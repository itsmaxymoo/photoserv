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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)


        if self.instance and self.instance.pk:
            # pre-check albums the photo already belongs to
            self.fields['albums'].initial = self.instance.albums.all()

    class Meta:
        model = Photo
        fields = ["title", "description", "raw_image", "albums"]
        exclude = ["last_updated"]
    
    def save(self, commit=True):
        # Save the Photo object first
        photo = super().save(commit=commit)

        # Assign albums with sequential order using a model method
        selected_albums = self.cleaned_data.get('albums', [])
        if commit:
            photo.assign_albums(selected_albums)

        return photo


class SizeForm(forms.ModelForm):
    class Meta:
        model = Size
        fields = ["slug", "comment", "max_dimension", "square_crop"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If we're editing an existing instance and it's builtin
        if self.instance and getattr(self.instance, "builtin", False):
            self.fields["slug"].disabled = True
            self.fields["comment"].disabled = True


class AlbumForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

    class Meta:
        model = Album
        exclude = ["_photos"]