from collections import OrderedDict
from datetime import datetime
from operator import attrgetter, itemgetter

from limpyd_jobs import STATUSES

from ..models import GithubUser, Repository

from . import JobRegistry
from .base import Queue, Error
from .repository import FetchForUpdate
from hooks.tasks import CheckRepositoryHook, CheckRepositoryEvents


def get_job_models():
    """
    Return the list of all Job models, sorted by queue_name
    """
    return sorted(JobRegistry, key=attrgetter('queue_name'))


def get_job_model_for_name(name):
    """
    Given a queue name, return the matching Job model
    """
    return [J for J in JobRegistry if J.queue_name == name][0]


def print_queues():
    """
    Print each queue with waiting or delayed jobs, by priority
    """
    queues = OrderedDict()
    for q in Queue.collection().sort(by='name', alpha=True).instances():
        waiting = q.waiting.llen()
        delayed = q.delayed.zcard()
        if waiting + delayed == 0:
            continue
        name, priority = q.hmget('name', 'priority')
        queues.setdefault(name, []).append({
            'priority': int(priority),
            'waiting': waiting,
            'delayed': delayed,
        })

    for name in queues:
        sub_queues = sorted(queues[name], key=itemgetter('priority'), reverse=True)

        total_waiting = sum([q['waiting'] for q in sub_queues])
        total_delayed = sum([q['delayed'] for q in sub_queues])

        if len(sub_queues) == 1:
            priority_part = sub_queues[0]['priority']
        else:
            priority_part = '----'

        print('%30s  %4s  %4d  %4d' % (name, priority_part, total_waiting, total_delayed))

        if len(sub_queues) > 1:
            for i, q in enumerate(sub_queues):
                print('%30s  %4d  %4d  %4d' % (' ', q['priority'], q['waiting'], q['delayed']))


def delete_empty_queues(dry_run=False, max_priority=0):
    """
    Delete all queues without any waiting or delayed job
    """
    for JobModel in get_job_models():
        QueueModel = JobModel.queue_model
        name = JobModel.queue_name

        for q in QueueModel.get_all_by_priority(name):
            priority = int(q.priority.hget())
            if priority >= max_priority:
                continue

            # two checks to be sure
            if q.waiting.llen() + q.delayed.zcard() > 0:
                continue
            if q.waiting.llen() + q.delayed.zcard() > 0:
                continue

            if dry_run:
                print('Empty: %s (%d)' % (name, priority))
            else:
                q.delete()
                print('Deleted: %s (%d)' % (name, priority))


def requeue_halted_jobs(dry_run=False):
    """
    Requeue all jobs that were halted but still in running state
    """
    for JobModel in get_job_models():
        running_jobs = list(JobModel.collection(queued=1, status=STATUSES.RUNNING).instances())
        for job in running_jobs:
            priority = int(job.priority.hget() or 0)
            if job.ident in (job.queue.waiting.lmembers() + job.queue.delayed.zmembers()):
                # ignore job if already waiting or delayed
                continue
            if dry_run:
                print('Halted: %s (%s)' % (job.ident, priority))
            else:
                job.status.hset(STATUSES.WAITING)
                job.queue.enqueue_job(job)
                print('Requeued: %s (%s)' % (job.ident, priority))


def get_last_error_for_job(job, index=0, date=None):
    """
    Return the last (or last-index if index is given) error for the given job,
    for the given date (use today if not given)
    """
    if not date:
        date = datetime.utcnow().strftime('%Y-%m-%d')
    return Error.collection_for_job(job).filter(date=date).sort(by='-time', alpha=True).instances()[index]


def get_last_error_for_job_model(job_model, index=0, date=None):
    """
    Return the last (or last-index if index is given) error for the given job model,
    for the given date (use today if not given)
    """
    if not date:
        date = datetime.utcnow().strftime('%Y-%m-%d')
    job_model_repr = '%s.%s' % (job_model.__module__, job_model.__name__)
    return Error.collection(job_model_repr=job_model_repr).filter(date=date).sort(by='-time', alpha=True).instances()[index]


def requeue_job(job, priority=0):
    """
    Reset the priority (default to 0) and status (WAITING) of a job and requeue it
    """
    job.priority.hset(priority)
    job.status.hset(STATUSES.WAITING)
    job.queue.enqueue_job(job)


def update_user_related_stuff(username, gh=None, dry_run=False):
    """
    Fetch for update all stuff related to the user.
    Needed before deleting a user which was deleted on the Github side.
    """
    if not dry_run and not gh:
        raise Exception('If dry_run set to False, you must pass gh')

    u = GithubUser.objects.get(username=username)

    issues_fetched = set()

    repositories = u.owned_repositories.all()
    if len(repositories):
        print('Owned repostories: %s' % ', '.join(['[%s] %s' % (r.id, r.full_name) for r in repositories]))
        if not dry_run:
            for r in repositories:
                try:
                    r.fetch(gh=gh, force_fetch=True)
                except Exception as e:
                    print('Failure while updating repository %s: %s' % (r.id, e))
            repositories = u.owned_repositories.all()
            if len(repositories):
                print('STILL Owned repostories: %s' % ', '.join(['[%s] %s' % (r.id, r.full_name) for r in repositories]))

    milestones = u.milestones.all()
    if len(milestones):
        print('Created milestones: %s' % ', '.join(['[%s] %s:%s' % (m.id, m.repository.full_name, m.title) for m in milestones]))
        if not dry_run:
            for m in milestones:
                try:
                    m.fetch(gh=gh, force_fetch=True)
                except Exception as e:
                    print('Failure while updating milestone %s: %s' % (m.id, e))
            milestones = u.milestones.all()
            if len(milestones):
                print('STILL Created milestones: %s' % ', '.join(['[%s] %s:%s' % (m.id, m.repository.full_name, m.title) for m in milestones]))

    for field, name in [('commits_authored', 'Authored'), ('commits_commited', 'Commited')]:
        commits = getattr(u, field).all()
        if len(commits):
            print('%s commits: %s' % (name, ', '.join(['[%s] %s:%s' % (c.id, c.repository.full_name, c.sha) for c in commits])))
            if not dry_run:
                for c in commits:
                    try:
                        c.fetch(gh=gh, force_fetch=True)
                    except Exception as e:
                        print('Failure while updating commit %s: %s' % (c.id, e))
                commits = getattr(u, field).all()
                if len(commits):
                    print('STILL %s commits: %s' % (name, ', '.join(['[%s] %s:%s' % (c.id, c.repository.full_name, c.sha) for c in commits])))

    for field, name in [('created_issues', 'Created'), ('assigned_issues', 'Assigned'), ('closed_issues', 'Closed'), ('merged_prs', 'Merged')]:
        issues = getattr(u, field).all()
        if len(issues):
            print('%s issues: %s' % (name, ', '.join(['[%s] %s:%s' % (i.id, i.repository.full_name, i.number) for i in issues])))
            if not dry_run:
                for i in issues:
                    if i.id in issues_fetched:
                        continue
                    try:
                        i.fetch_all(gh=gh, force_fetch=True)
                    except Exception as e:
                        print('Failure while updating issue %s: %s' % (i.id, e))
                    issues_fetched.add(i.id)
                issues = getattr(u, field).all()
                if len(issues):
                    print('STILL %s issues: %s' % (name, ', '.join(['[%s] %s:%s' % (i.id, i.repository.full_name, i.number) for i in issues])))

    for field, name in [('issue_comments', 'Simple'), ('pr_comments', 'Code')]:
        comments = getattr(u, field).all()
        if len(comments):
            print('%s comments: %s' % (name, ', '.join(['[%s] %s:%s' % (c.id, c.repository.full_name, c.issue.number) for c in comments])))
            if not dry_run:
                for c in comments:
                    if c.issue_id in issues_fetched:
                        continue
                    try:
                        c.issue.fetch_all(gh=gh, force_fetch=True)
                    except Exception as e:
                        print('Failure while updating issue %s for comment %s: %s' % (c.issue.id, c.id, e))
                    issues_fetched.add(c.issue_id)
                comments = getattr(u, field).all()
                if len(comments):
                    print('STILL %s comments: %s' % (name, ', '.join(['[%s] %s:%s' % (c.id, c.repository.full_name, c.issue.number) for c in comments])))

    entry_points = u.pr_comments_entry_points.all()
    if len(entry_points):
        print('Started entry points: %s' % ', '.join(['[%s] %s:%s' % (e.id, e.repository.full_name, e.issue.number) for e in entry_points]))
        if not dry_run:
            for ep in entry_points:
                try:
                    ep.update_starting_point()
                except Exception as e:
                    print('Failure while updating entry-point %s: %s' % (ep.id, e))
            entry_points = u.pr_comments_entry_points.all()
            if len(entry_points):
                print('STILL Started entry points: %s' % ', '.join(['[%s] %s:%s' % (e.id, e.repository.full_name, e.issue.number) for e in entry_points]))

    events = u.issues_events.all()
    if len(events):
        print('Issue events: %s' % ', '.join(['[%s] %s:%s' % (e.id, e.repository.full_name, e.issue.number) for e in events]))
        if not dry_run:
            for ev in events:
                if ev.issue_id in issues_fetched:
                    continue
                try:
                    ev.issue.fetch_all(gh=gh, force_fetch=True)
                except Exception as e:
                    print('Failure while updating issue %s for event %s: %s' % (ev.issue.id, ev.id, e))
                issues_fetched.add(ev.issue_id)
            events = u.issues_events.all()
            if len(events):
                print('STILL Issue events: %s' % ', '.join(['[%s] %s:%s' % (e.id, e.repository.full_name, e.issue.number) for e in events]))


def requeue_all_repositories():
    """
    Add (ignore if already present) Hook and Event check jobs for all activated
    repositories
    """
    for repository in Repository.objects.filter(first_fetch_done=True):
        CheckRepositoryEvents.add_job(repository.id)
        CheckRepositoryHook.add_job(repository.id, delayed_for=30)
        FetchForUpdate.add_job(repository.id)
