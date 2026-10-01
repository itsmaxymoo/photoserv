from django.db import transaction
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .api_access import (
    get_public_entity,
    has_internal_identifier_access,
    scope_queryset_for_api_access,
)
from .models import (
    Album,
    Channel,
    ChannelPhoto,
    Photo,
    PhotoMetadata,
    PhotoSize,
    Size,
    Tag,
)


class PublicEntitySerializerMixin:
    """Expose internal IDs only to trusted API requests."""

    def get_fields(self):
        fields = super().get_fields()
        if has_internal_identifier_access(self.context.get("request")):
            fields["id"] = serializers.IntegerField(read_only=True)
        return fields


class UUIDModelSerializer(PublicEntitySerializerMixin, serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)


class PublicEntityRelatedField(serializers.RelatedField):
    """Resolve a PublicEntity UUID, with conditional database-ID fallback."""

    default_error_messages = {
        "does_not_exist": "No matching object was found for this identifier.",
    }

    def to_internal_value(self, data):
        queryset = self.get_queryset()
        try:
            return get_public_entity(
                queryset,
                data,
                self.context.get("request"),
            )
        except queryset.model.DoesNotExist:
            self.fail("does_not_exist")

    def to_representation(self, value):
        if has_internal_identifier_access(self.context.get("request")):
            return value.pk
        return str(value.uuid)


class SizeReferenceSerializer(UUIDModelSerializer):
    class Meta:
        model = Size
        fields = ["uuid", "slug"]


class PhotoSizeSerializer(serializers.ModelSerializer):
    size = SizeReferenceSerializer(read_only=True)

    class Meta:
        model = PhotoSize
        fields = ["size", "height", "width", "md5"]


def serialize_photo_sizes(serializer, photo):
    queryset = scope_queryset_for_api_access(
        photo.sizes.select_related("size"),
        serializer.context.get("request"),
    )
    return PhotoSizeSerializer(
        queryset,
        many=True,
        context=serializer.context,
    ).data


class TagSummarySerializer(UUIDModelSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name"]


class AlbumSummarySerializer(UUIDModelSerializer):
    class Meta:
        model = Album
        fields = ["uuid", "slug", "title", "short_description"]


class ChannelSummarySerializer(UUIDModelSerializer):
    class Meta:
        model = Channel
        fields = ["uuid", "name", "builtin"]


class PhotoMetadataNestedSerializer(UUIDModelSerializer):
    class Meta:
        model = PhotoMetadata
        exclude = ["id", "photo", "raw_latitude", "raw_longitude"]
        read_only_fields = ["created_at", "updated_at"]


class PhotoSummarySerializer(UUIDModelSerializer):
    sizes = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "uuid",
            "title",
            "slug",
            "canonical_publish_date",
            "sizes",
        ]

    @extend_schema_field(PhotoSizeSerializer(many=True))
    def get_sizes(self, obj):
        return serialize_photo_sizes(self, obj)


class PhotoChannelSerializer(serializers.ModelSerializer):
    channel = ChannelSummarySerializer(read_only=True)
    published = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChannelPhoto
        fields = ["channel", "publish_date", "published"]


class ChannelPhotoSerializer(serializers.ModelSerializer):
    photo = PhotoSummarySerializer(read_only=True)
    published = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChannelPhoto
        fields = ["photo", "publish_date", "published"]


class PhotoSerializer(UUIDModelSerializer):
    image = serializers.ImageField(
        source="raw_image",
        write_only=True,
        required=False,
    )
    metadata = PhotoMetadataNestedSerializer(read_only=True)
    albums = AlbumSummarySerializer(many=True, read_only=True)
    tags = TagSummarySerializer(many=True, read_only=True)
    sizes = serializers.SerializerMethodField()
    channels = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "uuid",
            "title",
            "slug",
            "description",
            "image",
            "canonical_publish_date",
            "canonical_hidden",
            "custom_attributes",
            "latitude",
            "longitude",
            "hide_location",
            "albums",
            "tags",
            "metadata",
            "sizes",
            "channels",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]

    @extend_schema_field(PhotoSizeSerializer(many=True))
    def get_sizes(self, obj):
        return serialize_photo_sizes(self, obj)

    @extend_schema_field(PhotoChannelSerializer(many=True))
    def get_channels(self, obj):
        queryset = scope_queryset_for_api_access(
            obj.channels.select_related("channel"),
            self.context.get("request"),
        )
        return PhotoChannelSerializer(
            queryset,
            many=True,
            context=self.context,
        ).data

    def validate(self, attrs):
        if "raw_image" in self.initial_data:
            raise serializers.ValidationError(
                {"raw_image": "Use the binary 'image' upload field."}
            )
        return attrs


class PhotoCreateSerializer(PhotoSerializer):
    image = serializers.ImageField(source="raw_image", write_only=True)

    @transaction.atomic
    def create(self, validated_data):
        instance = Photo(**validated_data)
        instance.save(schedule_followup_tasks=True)
        if not instance.canonical_hidden:
            ChannelPhoto.objects.bulk_create(
                [
                    ChannelPhoto(
                        channel=channel,
                        photo=instance,
                        publish_date=instance.canonical_publish_date,
                    )
                    for channel in Channel.objects.filter(include_new_photos=True)
                ]
            )
        return instance


class PhotoUpdateSerializer(PhotoSerializer):
    image = serializers.ImageField(
        source="raw_image",
        write_only=True,
        required=False,
    )


class AlbumSerializer(UUIDModelSerializer):
    parent = AlbumSummarySerializer(read_only=True)
    parent_uuid = PublicEntityRelatedField(
        source="parent",
        queryset=Album.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Album
        fields = [
            "uuid",
            "title",
            "slug",
            "short_description",
            "description",
            "sort_method",
            "sort_descending",
            "parent",
            "parent_uuid",
            "custom_attributes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["slug", "created_at", "updated_at"]


class AlbumDetailSerializer(AlbumSerializer):
    photos = serializers.SerializerMethodField()
    children = AlbumSummarySerializer(many=True, read_only=True)

    class Meta(AlbumSerializer.Meta):
        fields = AlbumSerializer.Meta.fields + ["photos", "children"]

    @extend_schema_field(PhotoSummarySerializer(many=True))
    def get_photos(self, obj):
        request = self.context.get("request")
        recursive = False
        if request and "recursive" in request.query_params:
            recursive_field = serializers.BooleanField()
            recursive = recursive_field.run_validation(
                request.query_params["recursive"]
            )
        photos = scope_queryset_for_api_access(
            obj.get_ordered_photos(recursive=recursive),
            request,
        )
        return PhotoSummarySerializer(
            photos,
            many=True,
            context=self.context,
        ).data


class TagSerializer(UUIDModelSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_name(self, value):
        value = value.strip().lower()
        if ";" in value or "\n" in value:
            raise serializers.ValidationError(
                "Tag names cannot contain semicolons or newlines."
            )
        return value


class TagDetailSerializer(TagSerializer):
    photos = serializers.SerializerMethodField()

    class Meta(TagSerializer.Meta):
        fields = TagSerializer.Meta.fields + ["photos"]

    @extend_schema_field(PhotoSummarySerializer(many=True))
    def get_photos(self, obj):
        photos = scope_queryset_for_api_access(
            obj.photos.all(),
            self.context.get("request"),
        )
        return PhotoSummarySerializer(
            photos,
            many=True,
            context=self.context,
        ).data


class TagCreateSerializer(TagSerializer):
    photo = PublicEntityRelatedField(
        queryset=Photo.objects.all(),
        required=False,
        write_only=True,
    )
    photos = PublicEntityRelatedField(
        queryset=Photo.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = Tag
        fields = [
            "uuid",
            "name",
            "photo",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        photo = validated_data.pop("photo", None)
        photos = list(validated_data.pop("photos", []))
        if photo is not None:
            photos.append(photo)
        tag = Tag.objects.filter(name=validated_data["name"]).first()
        if tag is None:
            tag = Tag.objects.create(**validated_data)
        for related_photo in {photo.uuid: photo for photo in photos}.values():
            related_photo.tags.add(tag)
        return tag


class TagUpdateSerializer(TagSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name"]
        read_only_fields = ["uuid"]

    def validate(self, attrs):
        unexpected = set(self.initial_data) - {"name"}
        if unexpected:
            raise serializers.ValidationError(
                {field: "This field is not accepted." for field in unexpected}
            )
        return attrs

    def update(self, instance, validated_data):
        replacement = (
            Tag.objects.filter(name=validated_data["name"])
            .exclude(pk=instance.pk)
            .first()
        )
        instance.name = validated_data["name"]
        instance.save()
        return replacement or instance


class SizeSerializer(UUIDModelSerializer):
    class Meta:
        model = Size
        fields = [
            "uuid",
            "slug",
            "comment",
            "max_dimension",
            "square_crop",
            "builtin",
            "can_edit",
            "public",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["builtin", "created_at", "updated_at"]


class ChannelSerializer(UUIDModelSerializer):
    class Meta:
        model = Channel
        fields = [
            "uuid",
            "name",
            "description",
            "include_new_photos",
            "builtin",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["builtin", "created_at", "updated_at"]


class ChannelDetailSerializer(ChannelSerializer):
    photos = ChannelPhotoSerializer(many=True, read_only=True)

    class Meta(ChannelSerializer.Meta):
        fields = ChannelSerializer.Meta.fields + ["photos"]


class PhotoRelationshipSerializer(serializers.Serializer):
    photo = PublicEntityRelatedField(queryset=Photo.objects.all())


class ChannelPhotoRelationshipSerializer(PhotoRelationshipSerializer):
    publish_date = serializers.DateTimeField(required=True, allow_null=True)
