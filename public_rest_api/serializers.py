from core.models import Photo, Size, Album, Tag, PhotoMetadata, PhotoTag
from rest_framework import serializers


class PhotoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoMetadata
        exclude = ['id', 'photo', 'hidden']


class AlbumSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ["uuid", "slug", "title", "short_description"]


class AlbumSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = ["uuid", "title", "slug", "short_description", "description", "sort_method", "sort_descending", "photos", "parent", "children"]

    def get_photos(self, obj):
        return PhotoSummarySerializer(obj.get_ordered_photos(public_only=True), many=True).data
    
    def get_parent(self, obj):
        if obj.parent:
            return AlbumSummarySerializer(obj.parent).data
        return None
    
    def get_children(self, obj):
        return AlbumSummarySerializer(obj.children.all(), many=True).data


class TagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name"]


class PhotoSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ['uuid', 'title', "slug", 'publish_date']


class TagSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["uuid", "name", "photos"]

    def get_photos(self, obj):
        return PhotoSummarySerializer(obj.photos.all(), many=True).data


class PhotoSerializer(serializers.ModelSerializer):
    metadata = PhotoMetadataSerializer(read_only=True)
    albums = AlbumSummarySerializer(many=True, read_only=True)
    tags = TagSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Photo
        exclude = ['id', 'raw_image']


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["slug", "max_dimension", "square_crop"]


class SiteHealthSerializer(serializers.Serializer):
    total_photos = serializers.IntegerField()
    photos_pending_sizes = serializers.IntegerField()
    pending_sizes = serializers.IntegerField()
    pending_metadata = serializers.IntegerField()
