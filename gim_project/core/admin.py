from django.contrib import admin
from core.models import Issue, Repository


class IssueAdmin(admin.ModelAdmin):
    raw_id_fields = ('repository', 'user', 'milestone', 'assignee', 'closed_by', 'merged_by', 'labels', 'commits')


class RepositoryAdmin(admin.ModelAdmin):
    raw_id_fields = ('owner', 'collaborators', )


admin.site.register(Issue, IssueAdmin)
admin.site.register(Repository, RepositoryAdmin)
