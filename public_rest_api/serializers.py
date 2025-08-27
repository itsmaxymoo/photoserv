from core.models import Photo, Size, Album, Tag, PhotoMetadata, PhotoTag
from rest_framework import serializers


class SizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Size
        fields = ["slug", "max_dimension", "square_crop"]


class PhotoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoMetadata
        exclude = ['id', 'photo']


class AlbumSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Album
        fields = ["uuid", "title"]


class TagSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["uuid", "name"]


class PhotoSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ['uuid', 'title', 'publish_date']


class TagSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = ["uuid", "name", "photos"]

    def get_photos(self, obj):
        return PhotoSummarySerializer([pt.photo for pt in obj.photos.all()], many=True).data


class PhotoTagSerializer(serializers.ModelSerializer):
    tag = TagSummarySerializer()

    class Meta:
        model = PhotoTag
        fields = ["tag"]


class PhotoSerializer(serializers.ModelSerializer):
    metadata = PhotoMetadataSerializer(read_only=True)
    albums = AlbumSummarySerializer(many=True, read_only=True)
    tags = PhotoTagSerializer(many=True, read_only=True)

    class Meta:
        model = Photo
        exclude = ['id', 'raw_image']
