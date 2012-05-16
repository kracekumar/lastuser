# -*- coding: utf-8 -*-
from flask import g
import flask.ext.wtf as wtf

from lastuserapp.models import db, Permission, Resource, ResourceAction, getuser, Organization
from lastuserapp.utils import valid_username


class AuthorizeForm(wtf.Form):
    """
    OAuth authorization form. Has no fields and is only used for CSRF protection.
    """
    pass


class ConfirmDeleteForm(wtf.Form):
    """
    Confirm a delete operation
    """
    delete = wtf.SubmitField('Delete')
    cancel = wtf.SubmitField('Cancel')


class RegisterClientForm(wtf.Form):
    """
    Register a new OAuth client application
    """
    title = wtf.TextField('Application title', validators=[wtf.Required()],
        description="The name of your application")
    description = wtf.TextAreaField('Description', validators=[wtf.Required()],
        description="A description to help users recognize your application")
    client_owner = wtf.RadioField('Owner', validators=[wtf.Required()],
        description="User or organization that owns this application. Changing the owner "
            "will revoke all currently assigned permissions for this app")
    website = wtf.html5.URLField('Application website', validators=[wtf.Required(), wtf.URL(require_tld = False)],
        description="Website where users may access this application")
    redirect_uri = wtf.html5.URLField('Redirect URI', validators=[wtf.Optional(), wtf.URL(require_tld = False)],
        description="OAuth2 Redirect URI")
    notification_uri = wtf.html5.URLField('Notification URI', validators=[wtf.Optional(), wtf.URL(require_tld = False)],
        description="LastUser resource provider Notification URI. When another application requests access to "
            "resources provided by this app, LastUser will post a notice to this URI with a copy of the access "
            "token that was provided to the other application. Other notices may be posted too "
            "(not yet implemented)")
    iframe_uri = wtf.html5.URLField('IFrame URI', validators=[wtf.Optional(), wtf.URL(require_tld = False)],
        description="Front-end notifications URL. This is loaded in a hidden iframe to notify the app that the "
            "user updated their profile in some way (not yet implemented)")
    resource_uri = wtf.html5.URLField('Resource URI', validators=[wtf.Optional(), wtf.URL(require_tld = False)],
        description="URI at which this application provides resources as per the LastUser Resource API "
        "(not yet implemented)")
    allow_any_login = wtf.BooleanField('Allow anyone to login', default=True,
        description="If your application requires access to be restricted to specific users, uncheck this")

    def validate_client_owner(self, field):
        if field.data == g.user.userid:
            self.user = g.user
            self.org = None
        else:
            orgs = [org for org in g.user.organizations_owned() if org.userid == field.data]
            if len(orgs) != 1:
                raise wtf.ValidationError("Invalid owner")
            self.user = None
            self.org = orgs[0]


class PermissionForm(wtf.Form):
    """
    Create or edit a permission
    """
    name = wtf.TextField('Permission name', validators=[wtf.Required()],
        description='Name of the permission as a single word in lower case. '
            'This is passed to the application when a user logs in. '
            'Changing the name will not automatically update it everywhere. '
            'You must reassign the permission to users who had it with the old name')
    title = wtf.TextField('Title', validators=[wtf.Required()],
        description='Permission title that is displayed to users')
    description = wtf.TextAreaField('Description',
        description='An optional description of what the permission is for')
    context = wtf.RadioField('Context', validators=[wtf.Required()],
        description='Context where this permission is available')

    def validate(self):
        rv = super(PermissionForm, self).validate()
        if not rv:
            return False

        if not valid_username(self.name.data):
            raise wtf.ValidationError("Name contains invalid characters")

        edit_obj = getattr(self, 'edit_obj', None)
        if edit_obj:
            edit_id = edit_obj.id
        else:
            edit_id = None

        existing = Permission.query.filter_by(name=self.name.data, allusers=True).first()
        if existing and existing.id != edit_id:
            self.name.errors.append("A global permission with that name already exists")
            return False

        if self.context.data == g.user.userid:
            existing = Permission.query.filter_by(name=self.name.data, user=g.user).first()
        else:
            org = Organization.query.filter_by(userid=self.context.data).first()
            if org:
                existing = Permission.query.filter_by(name=self.name.data, org=org).first()
            else:
                existing = None
        if existing and existing.id != edit_id:
            self.name.errors.append("You have another permission with the same name")
            return False

        return True

    def validate_context(self, field):
        if field.data == g.user.userid:
            self.user = g.user
            self.org = None
        else:
            orgs = [org for org in g.user.organizations_owned() if org.userid == field.data]
            if len(orgs) != 1:
                raise wtf.ValidationError("Invalid context")
            self.user = None
            self.org = orgs[0]


class UserPermissionAssignForm(wtf.Form):
    """
    Assign permissions to a user
    """
    username = wtf.TextField("User", validators=[wtf.Required()],
        description='Lookup a user by their username or email address')
    perms = wtf.SelectMultipleField("Permissions", validators=[wtf.Required()])

    def validate_username(self, field):
        existing = getuser(field.data)
        if existing is None:
            raise wtf.ValidationError("User does not exist")
        self.user = existing


class TeamPermissionAssignForm(wtf.Form):
    """
    Assign permissions to a team
    """
    team_id = wtf.RadioField("Team", validators=[wtf.Required()],
        description='Select a team to assign permissiont to')
    perms = wtf.SelectMultipleField("Permissions", validators=[wtf.Required()])

    def validate_team_id(self, field):
        teams = [team for team in self.org.teams if team.userid == field.data]
        if len(teams) != 1:
            raise wtf.ValidationError("Unknown team")
        self.team = teams[0]


class PermissionEditForm(wtf.Form):
    """
    Edit a user or team's permissions
    """
    perms = wtf.SelectMultipleField("Permissions", validators=[wtf.Required()])


class ResourceForm(wtf.Form):
    """
    Edit a resource provided by an application
    """
    name = wtf.TextField('Resource name', validators=[wtf.Required()],
        description="Name of the resource as a single word in lower case. "
            "This is provided by applications as part of the scope "
            "when requesting access to a user's resources.")
    title = wtf.TextField('Title', validators=[wtf.Required()],
        description='Resource title that is displayed to users')
    description = wtf.TextAreaField('Description',
        description='An optional description of what the resource is')
    siteresource = wtf.BooleanField('Site resource',
        description='Enable if this resource is generic to the site and not owned by specific users')
    trusted = wtf.BooleanField('Trusted applications only',
        description='Enable if access to the resource should be restricted to trusted '
            'applications. You may want to do this for sensitive information like billing data')

    def validate_name(self, field):
        if not valid_username(field.data):
            raise wtf.ValidationError("Name contains invalid characters.")

        existing = Resource.query.filter_by(name=field.data).first()
        if existing and existing.id != self.edit_id:
            raise wtf.ValidationError("A resource with that name already exists")


class ResourceActionForm(wtf.Form):
    """
    Edit an action associated with a resource
    """
    name = wtf.TextField('Action name', validators=[wtf.Required()],
        description="Name of the action as a single word in lower case. "
            "This is provided by applications as part of the scope in the form "
            "'resource/action' when requesting access to a user's resources. "
            "Read actions are implicit when applications request just 'resource' "
            "in the scope and do not need to be specified as an explicit action.")
    title = wtf.TextField('Title', validators=[wtf.Required()],
        description='Action title that is displayed to users')
    description = wtf.TextAreaField('Description',
        description='An optional description of what the action is')

    def validate_name(self, field):
        if not valid_username(field.data):
            raise wtf.ValidationError("Name contains invalid characters.")

        existing = ResourceAction.query.filter_by(name=field.data, resource=self.edit_resource).first()
        if existing and existing.id != self.edit_id:
            raise wtf.ValidationError("An action with that name already exists for this resource")
