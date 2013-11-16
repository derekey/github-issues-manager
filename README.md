github-issues-manager
=====================

A Django project to manage github issues

*WORK-IN-PROGRESS*

Note:

To run async tasks, you must have a redis running on default host:port, go in your venv at the root of the git project, and run:

```
DJANGO_SETTINGS_MODULE=gim_project.settings limpyd-jobs-worker --worker-class=core.tasks.Worker --queues=edit-issue-state,edit-issue-comment,edit-pr-comment,fetch-issue-by-number,first-repository-fetch,repository-fetch-step2,fetch-available-repos,edit-label,update-issue-tmpl,fetch-closed-issues,update-pull-requests,fetch-unfetched-commits --pythonpath gim_project
```

(you may want to run many workers by repeating the line above in many terms, it's really faster, notably for the `update-issue-tmpl` queue)