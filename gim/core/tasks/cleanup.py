from datetime import datetime, timedelta

from .base import Error, Queue
from . import JobRegistry


def _get_past_date(days):
    return (datetime.utcnow()-timedelta(days=days)).strftime('%Y-%m-%d')


def clean_errors(print_step=1000, keep_days=7, batch_size=100):
    """
    Remove from the Errors model all entries older than the given number of days
    """
    count = len(Error.collection())
    max_date = _get_past_date(keep_days)
    done = 0
    errors = 0
    print('Deleting Error (max date = %s, total: %d)' % (max_date, count))
    stop = False
    iterate = 0
    while not stop:
        instances = list(Error.collection().sort(by='date', alpha=True).instances(skip_exist_test=True)[:batch_size])
        if not instances:
            break
        for instance in instances:
            iterate += 1
            if iterate and not iterate % print_step:
                print('Deleted %d on %d' % (done, count))
            try:
                if keep_days and instance.date.hget() >= max_date:
                    stop = True
                    break
                instance.delete()
            except Exception, e:
                print('Cannot delete Error %s: %s' % (instance.pk.get(), e))
                errors += 1
            else:
                done += 1

    print('Total Error deleted: %d on %d, keep %d (including %d errors)' % (done, count, count - done, errors))


def clean_job_model(job_model, print_step=1000, keep_days=7, batch_size=100):
    """
    Remove from the given job model all entries older than the given number of days
    Also clear the success and errors list of all the queues (different priorities)
    linked to the model
    """
    model_repr = job_model.get_model_repr()
    count = len(job_model.collection())
    max_date = _get_past_date(keep_days)
    done = 0
    errors = 0
    planned = set(sum([q.waiting.lmembers() + q.delayed.zmembers() for q in Queue.get_all_by_priority(job_model.queue_name)], []))
    print('Deleting %s (max date = %s, total: %d (planned: %d))' % (model_repr, max_date, count, len(planned)))
    kept = 0
    iterate = 0
    while True:
        instances = list(job_model.collection().instances(skip_exist_test=True)[kept:kept+batch_size])
        if not instances:
            break
        for instance in instances:
            iterate += 1
            if iterate and not iterate % print_step:
                print('Deleted %d on %d (kept %d)' % (done, count, kept))
            try:
                if instance.ident in planned or keep_days and instance.added.hget()[:10] >= max_date:
                    # skip it, so stay in the list, so skip in the next batch
                    kept += 1
                    continue
                instance.delete()
            except Exception, e:
                print('Cannot delete %s %s: %s' % (model_repr, instance.pk.get(), e))
                errors += 1
                # skip it, so stay in the list, so skip in the next batch
                kept += 1
            else:
                done += 1

    for q in Queue.get_all_by_priority(job_model.queue_name):
        q.success.delete()
        q.errors.delete()

    print('Total %s deleted: %d on %d, keep %d (including %d errors and %d planned)' % (model_repr, done, count, kept, errors, len(planned)))


def clean_all(print_step=1000, keep_days=7, batch_size=100):
    """
    Remove from the Error and all Job models entries older than the given number of days
    """
    clean_errors(print_step=print_step, keep_days=keep_days, batch_size=batch_size)
    for J in JobRegistry:
        clean_job_model(J, print_step=print_step, keep_days=keep_days, batch_size=batch_size)
