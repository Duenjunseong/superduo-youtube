from django.contrib import admin
from .models import Workspace, WorkspaceMembership, Invitation

@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'is_public', 'member_count', 'max_members', 'created_at')
    list_filter = ('status', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('workspace_id', 'created_at', 'updated_at')
    
    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = '현재 멤버 수'

@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'workspace', 'role', 'status', 'joined_at')
    list_filter = ('role', 'status', 'joined_at')
    search_fields = ('user__username', 'workspace__name')
    readonly_fields = ('membership_id', 'joined_at', 'updated_at')

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('invitee_email', 'workspace', 'inviter', 'role', 'status', 'created_at', 'expires_at')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('invitee_email', 'workspace__name', 'inviter__username')
    readonly_fields = ('invitation_id', 'created_at', 'updated_at', 'is_expired')
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = '만료됨'
