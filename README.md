github-issues-manager
=====================

A Django project to manage github issues

*WORK-IN-PROGRESS*

Note:

To run async tasks, you must have a redis running on default host:port, go in your venv at the root of the git project, and run:

```
DJANGO_SETTINGS_MODULE=gim_project.settings limpyd-jobs-worker --worker-class=core.tasks.Worker --queues=fetch-closed-issues,first-repository-fetch,fetch-available-repos,edit-label --pythonpath gim_project
```

(you can run many workers, but while developing, one worker for all queues is easier)