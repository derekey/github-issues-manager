github-issues-manager
=====================

A Django project to manage github issues

*WORK-IN-PROGRESS*

Note:

To run async tasks, you must have a redis running on default host:port, go in your venv at the root of the git project, and run:

```
DJANGO_SETTINGS_MODULE=gim_project.settings limpyd-jobs-worker --worker-class=core.tasks.base.Worker --queues=create-issue,edit-issue-state,edit-issue-comment,edit-pr-comment,edit-label,edit-milestone,edit-issue-title,edit-issue-body,edit-issue-milestone,edit-issue-assignee,edit-issue-labels,update-issue-tmpl,reset-token-flags,check-repo-events,fetch-issue-by-number,first-repository-fetch,repository-fetch-step2,fetch-available-repos,check-repo-hook,update-repo,fetch-commit-by-sha,search-ref-commit-event,search-ref-commit-pr-comment,search-ref-commit-comment,update-graphs-data,update-pull-requests,fetch-closed-issues,reset-issue-activity,reset-repo-counters,update-mergable-status --pythonpath gim_project
```

(you may want to run many workers by repeating the line above in many terms, it's really faster, notably for the `update-issue-tmpl` queue)

Another note:

The boostrap theme used is not a free one, so it's not included in this repository, and you won't be able to compile css (but you can use the compiled css we provide).

The original theme is: https://wrapbootstrap.com/theme/core-admin-WB0135486 (we use v1.2, but slightly modified)

Wana talk ? [![Gitter chat](https://badges.gitter.im/twidi/github-issues-manager.png)](https://gitter.im/twidi/github-issues-manager)

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/twidi/github-issues-manager/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

