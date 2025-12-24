from django import forms
from django.forms import modelformset_factory
from crispy_forms.helper import FormHelper
from .models import *
from .tasks import post_photo_create


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
    hidden = forms.BooleanField(required=False, initial=False, help_text="Hide from public API and/or yank from supported integrations.")
    publish_date = forms.DateTimeField(
        required=False,
        help_text="Set a specific publish date/time for the photo.",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        initial=forms.fields.datetime.datetime.now,
    )
    excluded_plugins = forms.ModelMultipleChoiceField(
        queryset=None,  # Set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Exclude from publish/unpublish notification",
        help_text="Select plugins to exclude from being notified about this photo's publish/unpublish event. This setting is per-edit."
    )

    def _setup_plugin_exclusions(self, photo):
        """
        Helper method to set up plugin exclusions for a photo.
        Must be called after the photo has been saved and has an ID.
        """
        try:
            from integration.models import PhotoPluginExclusion
            
            # Clear any existing exclusions for this photo
            PhotoPluginExclusion.objects.filter(photo=photo).delete()
            
            # Create new exclusions based on form selection
            excluded_plugins = self.cleaned_data.get('excluded_plugins', [])
            for plugin in excluded_plugins:
                PhotoPluginExclusion.objects.create(photo=photo, plugin=plugin)
        except ImportError:
            # Integration app not available, skip exclusion handling
            pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)

        # Dynamically populate excluded_plugins queryset
        try:
            from integration.models import PythonPlugin
            self.fields['excluded_plugins'].queryset = PythonPlugin.objects.order_by('nickname', 'module')
            
            # Pre-populate with existing exclusions if editing
            if self.instance and self.instance.pk:
                from integration.models import PhotoPluginExclusion
                excluded_ids = PhotoPluginExclusion.objects.filter(
                    photo=self.instance
                ).values_list('plugin_id', flat=True)
                self.fields['excluded_plugins'].initial = excluded_ids
        except Exception:
            # If integration app is not available, use empty queryset
            from django.db.models import Model
            self.fields['excluded_plugins'].queryset = Model.objects.none()

        if self.instance and self.instance.pk:
            # pre-check albums the photo already belongs to
            self.fields['albums'].initial = self.instance.albums.all()

            current_tags = [pt.name for pt in self.instance.tags.all()]
            self.fields['tags'].initial = ";".join(current_tags)
            # Also add a list version for the template
            self.initial['tags_list'] = list(current_tags)

            # Disable publish_date field if photo is already published
            if self.instance.published:
                self.fields['publish_date'].disabled = True
                self.fields['publish_date'].help_text = "Cannot change publish date of a published photo."

    class Meta:
        model = Photo
        fields = ["title", "description", "raw_image", "slug", "hidden", "publish_date", "albums"]
        exclude = ["last_updated"]
    
    def save(self, commit=True):
        # Check if this is a new photo
        is_new = self.instance.pk is None
        
        if not commit:
            # Just return unsaved instance
            return super().save(commit=False)
        
        # For existing photos, set up exclusions BEFORE saving
        # This ensures they're in place before any signals are dispatched
        if not is_new:
            self._setup_plugin_exclusions(self.instance)
        
        photo = super().save(commit=True)
        
        if is_new:            
            # Set up exclusions before scheduling tasks
            self._setup_plugin_exclusions(photo)
            
            # Now schedule the post-creation task (which will trigger signals)
            post_photo_create.delay_on_commit(photo.id)

        # Assign albums with sequential order using a model method
        selected_albums = self.cleaned_data.get('albums', [])
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


class CondensedPhotoForm(PhotoForm):
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 1, "class": "min-h-0"})
    )

    class Meta(PhotoForm.Meta):
        fields = ["title", "description", "raw_image", "hidden", "publish_date", "albums"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the slug field inherited from PhotoForm
        if "slug" in self.fields:
            del self.fields["slug"]


PhotoFormSet = forms.modelformset_factory(
    Photo,
    form=CondensedPhotoForm,
    extra=0,
    can_delete=False
)


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
