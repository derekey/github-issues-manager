# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'GithubUser'
        db.create_table(u'core_githubuser', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('password', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('last_login', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('is_superuser', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('username', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('first_name', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('last_name', self.gf('django.db.models.fields.CharField')(max_length=30, blank=True)),
            ('email', self.gf('django.db.models.fields.EmailField')(max_length=75, blank=True)),
            ('is_staff', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('date_joined', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('github_id', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True, null=True, blank=True)),
            ('token', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('avatar_url', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('is_organization', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('organizations_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('_available_repositories', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('available_repositories_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['GithubUser'])

        # Adding M2M table for field groups on 'GithubUser'
        m2m_table_name = db.shorten_name(u'core_githubuser_groups')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('githubuser', models.ForeignKey(orm[u'core.githubuser'], null=False)),
            ('group', models.ForeignKey(orm[u'auth.group'], null=False))
        ))
        db.create_unique(m2m_table_name, ['githubuser_id', 'group_id'])

        # Adding M2M table for field user_permissions on 'GithubUser'
        m2m_table_name = db.shorten_name(u'core_githubuser_user_permissions')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('githubuser', models.ForeignKey(orm[u'core.githubuser'], null=False)),
            ('permission', models.ForeignKey(orm[u'auth.permission'], null=False))
        ))
        db.create_unique(m2m_table_name, ['githubuser_id', 'permission_id'])

        # Adding M2M table for field organizations on 'GithubUser'
        m2m_table_name = db.shorten_name(u'core_githubuser_organizations')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('from_githubuser', models.ForeignKey(orm[u'core.githubuser'], null=False)),
            ('to_githubuser', models.ForeignKey(orm[u'core.githubuser'], null=False))
        ))
        db.create_unique(m2m_table_name, ['from_githubuser_id', 'to_githubuser_id'])

        # Adding model 'Repository'
        db.create_table(u'core_repository', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('github_id', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True, null=True, blank=True)),
            ('owner', self.gf('django.db.models.fields.related.ForeignKey')(related_name='owned_repositories', to=orm['core.GithubUser'])),
            ('name', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('private', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('is_fork', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_issues', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('collaborators_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('milestones_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('labels_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('issues_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('comments_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['Repository'])

        # Adding unique constraint on 'Repository', fields ['owner', 'name']
        db.create_unique(u'core_repository', ['owner_id', 'name'])

        # Adding M2M table for field collaborators on 'Repository'
        m2m_table_name = db.shorten_name(u'core_repository_collaborators')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('repository', models.ForeignKey(orm[u'core.repository'], null=False)),
            ('githubuser', models.ForeignKey(orm[u'core.githubuser'], null=False))
        ))
        db.create_unique(m2m_table_name, ['repository_id', 'githubuser_id'])

        # Adding model 'LabelType'
        db.create_table(u'core_labeltype', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(related_name='label_types', to=orm['core.Repository'])),
            ('regex', self.gf('django.db.models.fields.TextField')()),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=250, db_index=True)),
            ('edit_mode', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1)),
            ('edit_details', self.gf('jsonfield.fields.JSONField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['LabelType'])

        # Adding unique constraint on 'LabelType', fields ['repository', 'name']
        db.create_unique(u'core_labeltype', ['repository_id', 'name'])

        # Adding model 'Label'
        db.create_table(u'core_label', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(related_name='labels', to=orm['core.Repository'])),
            ('name', self.gf('django.db.models.fields.TextField')()),
            ('color', self.gf('django.db.models.fields.CharField')(max_length=6)),
            ('api_url', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('label_type', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='labels', null=True, on_delete=models.SET_NULL, to=orm['core.LabelType'])),
            ('typed_name', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('order', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['Label'])

        # Adding unique constraint on 'Label', fields ['repository', 'name']
        db.create_unique(u'core_label', ['repository_id', 'name'])

        # Adding index on 'Label', fields ['repository', 'label_type', 'order']
        db.create_index(u'core_label', ['repository_id', 'label_type_id', 'order'])

        # Adding model 'Milestone'
        db.create_table(u'core_milestone', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('github_id', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True, null=True, blank=True)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(related_name='milestones', to=orm['core.Repository'])),
            ('number', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('title', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('state', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('due_on', self.gf('django.db.models.fields.DateTimeField')(db_index=True, null=True, blank=True)),
            ('creator', self.gf('django.db.models.fields.related.ForeignKey')(related_name='milestones', to=orm['core.GithubUser'])),
        ))
        db.send_create_signal(u'core', ['Milestone'])

        # Adding unique constraint on 'Milestone', fields ['repository', 'number']
        db.create_unique(u'core_milestone', ['repository_id', 'number'])

        # Adding model 'Issue'
        db.create_table(u'core_issue', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('github_id', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True, null=True, blank=True)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(related_name='issues', to=orm['core.Repository'])),
            ('number', self.gf('django.db.models.fields.PositiveIntegerField')(db_index=True)),
            ('title', self.gf('django.db.models.fields.TextField')(db_index=True)),
            ('body', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('body_html', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='created_issues', to=orm['core.GithubUser'])),
            ('assignee', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='assigned_issues', null=True, to=orm['core.GithubUser'])),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('updated_at', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('closed_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_pull_request', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('milestone', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='issues', null=True, to=orm['core.Milestone'])),
            ('state', self.gf('django.db.models.fields.CharField')(max_length=10, db_index=True)),
            ('comments_count', self.gf('django.db.models.fields.PositiveIntegerField')(null=True, blank=True)),
            ('closed_by', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='closed_issues', null=True, to=orm['core.GithubUser'])),
            ('closed_by_fetched', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True)),
            ('comments_fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'core', ['Issue'])

        # Adding unique constraint on 'Issue', fields ['repository', 'number']
        db.create_unique(u'core_issue', ['repository_id', 'number'])

        # Adding M2M table for field labels on 'Issue'
        m2m_table_name = db.shorten_name(u'core_issue_labels')
        db.create_table(m2m_table_name, (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('issue', models.ForeignKey(orm[u'core.issue'], null=False)),
            ('label', models.ForeignKey(orm[u'core.label'], null=False))
        ))
        db.create_unique(m2m_table_name, ['issue_id', 'label_id'])

        # Adding model 'IssueComment'
        db.create_table(u'core_issuecomment', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('fetched_at', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('github_status', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1, db_index=True)),
            ('github_id', self.gf('django.db.models.fields.PositiveIntegerField')(unique=True, null=True, blank=True)),
            ('repository', self.gf('django.db.models.fields.related.ForeignKey')(related_name='comments', to=orm['core.Repository'])),
            ('issue', self.gf('django.db.models.fields.related.ForeignKey')(related_name='comments', to=orm['core.Issue'])),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='issue_comments', to=orm['core.GithubUser'])),
            ('body', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('body_html', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('updated_at', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
        ))
        db.send_create_signal(u'core', ['IssueComment'])


    def backwards(self, orm):
        # Removing unique constraint on 'Issue', fields ['repository', 'number']
        db.delete_unique(u'core_issue', ['repository_id', 'number'])

        # Removing unique constraint on 'Milestone', fields ['repository', 'number']
        db.delete_unique(u'core_milestone', ['repository_id', 'number'])

        # Removing index on 'Label', fields ['repository', 'label_type', 'order']
        db.delete_index(u'core_label', ['repository_id', 'label_type_id', 'order'])

        # Removing unique constraint on 'Label', fields ['repository', 'name']
        db.delete_unique(u'core_label', ['repository_id', 'name'])

        # Removing unique constraint on 'LabelType', fields ['repository', 'name']
        db.delete_unique(u'core_labeltype', ['repository_id', 'name'])

        # Removing unique constraint on 'Repository', fields ['owner', 'name']
        db.delete_unique(u'core_repository', ['owner_id', 'name'])

        # Deleting model 'GithubUser'
        db.delete_table(u'core_githubuser')

        # Removing M2M table for field groups on 'GithubUser'
        db.delete_table(db.shorten_name(u'core_githubuser_groups'))

        # Removing M2M table for field user_permissions on 'GithubUser'
        db.delete_table(db.shorten_name(u'core_githubuser_user_permissions'))

        # Removing M2M table for field organizations on 'GithubUser'
        db.delete_table(db.shorten_name(u'core_githubuser_organizations'))

        # Deleting model 'Repository'
        db.delete_table(u'core_repository')

        # Removing M2M table for field collaborators on 'Repository'
        db.delete_table(db.shorten_name(u'core_repository_collaborators'))

        # Deleting model 'LabelType'
        db.delete_table(u'core_labeltype')

        # Deleting model 'Label'
        db.delete_table(u'core_label')

        # Deleting model 'Milestone'
        db.delete_table(u'core_milestone')

        # Deleting model 'Issue'
        db.delete_table(u'core_issue')

        # Removing M2M table for field labels on 'Issue'
        db.delete_table(db.shorten_name(u'core_issue_labels'))

        # Deleting model 'IssueComment'
        db.delete_table(u'core_issuecomment')


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'core.githubuser': {
            'Meta': {'ordering': "('username',)", 'object_name': 'GithubUser'},
            '_available_repositories': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'available_repositories_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'avatar_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'github_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_organization': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'organizations': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'organizations_rel_+'", 'to': u"orm['core.GithubUser']"}),
            'organizations_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'token': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        u'core.issue': {
            'Meta': {'unique_together': "(('repository', 'number'),)", 'object_name': 'Issue'},
            'assignee': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'assigned_issues'", 'null': 'True', 'to': u"orm['core.GithubUser']"}),
            'body': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'body_html': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'closed_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'closed_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'closed_issues'", 'null': 'True', 'to': u"orm['core.GithubUser']"}),
            'closed_by_fetched': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'comments_count': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'comments_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'github_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_pull_request': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'labels': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'issues'", 'symmetrical': 'False', 'to': u"orm['core.Label']"}),
            'milestone': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'issues'", 'null': 'True', 'to': u"orm['core.Milestone']"}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'issues'", 'to': u"orm['core.Repository']"}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'title': ('django.db.models.fields.TextField', [], {'db_index': 'True'}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_issues'", 'to': u"orm['core.GithubUser']"})
        },
        u'core.issuecomment': {
            'Meta': {'ordering': "('created_at',)", 'object_name': 'IssueComment'},
            'body': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'body_html': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'github_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issue': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': u"orm['core.Issue']"}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'comments'", 'to': u"orm['core.Repository']"}),
            'updated_at': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'issue_comments'", 'to': u"orm['core.GithubUser']"})
        },
        u'core.label': {
            'Meta': {'ordering': "('label_type', 'order', 'typed_name')", 'unique_together': "(('repository', 'name'),)", 'object_name': 'Label', 'index_together': "(('repository', 'label_type', 'order'),)"},
            'api_url': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'color': ('django.db.models.fields.CharField', [], {'max_length': '6'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label_type': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'labels'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['core.LabelType']"}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'order': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'labels'", 'to': u"orm['core.Repository']"}),
            'typed_name': ('django.db.models.fields.TextField', [], {'db_index': 'True'})
        },
        u'core.labeltype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('repository', 'name'),)", 'object_name': 'LabelType'},
            'edit_details': ('jsonfield.fields.JSONField', [], {'null': 'True', 'blank': 'True'}),
            'edit_mode': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '250', 'db_index': 'True'}),
            'regex': ('django.db.models.fields.TextField', [], {}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'label_types'", 'to': u"orm['core.Repository']"})
        },
        u'core.milestone': {
            'Meta': {'ordering': "('number',)", 'unique_together': "(('repository', 'number'),)", 'object_name': 'Milestone'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'milestones'", 'to': u"orm['core.GithubUser']"}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'due_on': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'github_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'repository': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'milestones'", 'to': u"orm['core.Repository']"}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '10', 'db_index': 'True'}),
            'title': ('django.db.models.fields.TextField', [], {'db_index': 'True'})
        },
        u'core.repository': {
            'Meta': {'ordering': "('owner', 'name')", 'unique_together': "(('owner', 'name'),)", 'object_name': 'Repository'},
            'collaborators': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'repositories'", 'symmetrical': 'False', 'to': u"orm['core.GithubUser']"}),
            'collaborators_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'comments_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'github_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'github_status': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1', 'db_index': 'True'}),
            'has_issues': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_fork': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'issues_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'labels_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'milestones_fetched_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {'db_index': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'owned_repositories'", 'to': u"orm['core.GithubUser']"}),
            'private': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        }
    }

    complete_apps = ['core']