from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field
from .models import *


class PhotoForm(forms.ModelForm):
    albums = forms.ModelMultipleChoiceField(
        queryset=Album.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Albums"
    )
    tags = forms.CharField(required=False, widget=forms.HiddenInput())
    slug = forms.CharField(
        required=False,
        help_text="Leave blank to auto calculate"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)


        if self.instance and self.instance.pk:
            # pre-check albums the photo already belongs to
            self.fields['albums'].initial = self.instance.albums.all()

            current_tags = [pt.name for pt in self.instance.tags.all()]
            self.fields['tags'].initial = ";".join(current_tags)
            # Also add a list version for the template
            self.initial['tags_list'] = list(current_tags)

    class Meta:
        model = Photo
        fields = ["title", "description", "raw_image", "slug", "hidden", "albums"]
        exclude = ["last_updated"]
    
    def save(self, commit=True):
        # Save the Photo object first
        photo = super().save(commit=commit)

        # Assign albums with sequential order using a model method
        selected_albums = self.cleaned_data.get('albums', [])
        if commit:
            photo.assign_albums(selected_albums)
        
        # Handle tags
        tags_str = self.cleaned_data.get("tags", "")
        tags_list = [t.strip().lower() for t in tags_str.split(";") if t.strip()]

        # Remove old tag entries not in new list
        photo.tags.exclude(name__in=tags_list).delete()

        # Add new tags (create Tag if necessary)
        for tag_name in tags_list:
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            PhotoTag.objects.get_or_create(photo=photo, tag=tag)
        
        # clean up orphaned tags
        Tag.objects.filter(photos__isnull=True).delete()


        return photo


class SizeForm(forms.ModelForm):
    class Meta:
        model = Size
        fields = ["slug", "comment", "max_dimension", "square_crop", "public"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

        # If we're editing an existing instance and it's builtin
        if self.instance and getattr(self.instance, "builtin", False):
            self.fields["slug"].disabled = True
            self.fields["comment"].disabled = True


class AlbumForm(forms.ModelForm):
    slug = forms.CharField(
        required=False,
        help_text="Leave blank to auto calculate"
    )
    parent = forms.ModelChoiceField(
        queryset=Album.objects.none(),
        required=False,
        label="Parent Album"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        # Exclude current album from parent choices
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Album.objects.exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = Album.objects.all()

    class Meta:
        model = Album
        exclude = ["_photos", "children"]


class TagForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = Tag
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter tag name"})
        }
