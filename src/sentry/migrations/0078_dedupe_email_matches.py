# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-05-18 17:36
from __future__ import unicode_literals

from django.db import migrations
from collections import defaultdict


def dedeupe_emails(email_model):
    # this query finds useremail matches that are case insensitive matches
    # note we get a result for each item in the pair (intentional)
    query = email_model.objects.raw(
        """
        SELECT dupe_ue.*
        FROM sentry_useremail ue
        INNER JOIN sentry_useremail dupe_ue ON (lower(ue.email) = lower(dupe_ue.email))
        WHERE dupe_ue.user_id = ue.user_id
        AND ue.email != dupe_ue.email
        """
    )

    # create pairings of each email so we can figure out which one to delete
    email_pairings = defaultdict(set)
    for user_email in query:
        # make pairing based off user id and lowercase email since that's what the uniquness constraint will be
        lowercase = user_email.email.lower()
        key = "%d_%s"%(user_email.user_id, lowercase)
        email_pairings[key].add(user_email)

    # for every group of matching emails, only keep one email
    # if one is the primary email, keep that one
    # if none are primary, find the first one that is verified
    # otherwise, just keep the first

    for email_set in email_pairings.values():
        email_list = list(email_set)

        # this should never happen based off the query but rather be safe than sorry
        if len(email_list) < 2:
            print("Unexpected solo email: %s" % email_list[0])
            continue

        primary_emails = filter(lambda x: x.email == x.user.email, email_list)
        verified_emails = filter(lambda x: x.is_verified, email_list)

        email_to_keep = email_list[0]
        if primary_emails:
            email_to_keep = primary_emails[0]
        elif verified_emails:
            email_to_keep = verified_emails[0]

        emails_to_delete = filter(lambda x: x != email_to_keep, email_list)
        for email in emails_to_delete:
            email.delete()


def forwards(apps, schema_editor):
    UserEmail = apps.get_model("sentry", "UserEmail")
    dedeupe_emails(UserEmail)



class Migration(migrations.Migration):
    # This flag is used to mark that a migration shouldn't be automatically run in
    # production. We set this to True for operations that we think are risky and want
    # someone from ops to run manually and monitor.
    # General advice is that if in doubt, mark your migration as `is_dangerous`.
    # Some things you should always mark as dangerous:
    # - Large data migrations. Typically we want these to be run manually by ops so that
    #   they can be monitored. Since data migrations will now hold a transaction open
    #   this is even more important.
    # - Adding columns to highly active tables, even ones that are NULL.
    is_dangerous = True

    # This flag is used to decide whether to run this migration in a transaction or not.
    # By default we prefer to run in a transaction, but for migrations where you want
    # to `CREATE INDEX CONCURRENTLY` this needs to be set to False. Typically you'll
    # want to create an index concurrently when adding one to an existing table.
    atomic = False


    dependencies = [
        ('sentry', '0077_alert_query_col_drop_state'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]