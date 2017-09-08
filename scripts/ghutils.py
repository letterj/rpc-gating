#!/usr/bin/env python

# This script contains github related utilties for Jenkins.


import click
import github3
import json
import logging

logger = logging.getLogger("ghutils")


@click.group()
@click.pass_context
@click.option(
    '--org',
    help='Github Organisation that owns the target repo',
    required=True,
)
@click.option(
    '--repo',
    help='Name of target repo',
    required=True,
)
@click.option(
    '--pat',
    help="Github Personal Access Token",
    required=True,
)
@click.option(
    '--debug/--no-debug'
)
def cli(ctxt, org, repo, pat, debug):
    gh = github3.login(token=pat)
    repo_ = gh.repository(org, repo)
    ctxt.obj = repo_
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)


@cli.command()
@click.pass_obj
@click.option('--tag',
              help='Jenkins build tag',
              required=True)
@click.option('--link',
              help='Link to related build in Jenkins UI',
              required=True)
@click.option('--label',
              help="Add label to issue, can be specified multiple times",
              multiple=True,
              required=True)
def create_issue(repo, tag, link, label):
    repo.create_issue(
        title="JBF: {tag}".format(tag=tag),
        body="[link to failing build]({url})".format(url=link),
        labels=label
    )


@cli.command()
@click.pass_obj
@click.option(
    '--pull-request-number',
    help="Pull request to update",
    required=True,
)
@click.option(
    '--issue-key',
    help='Issue being resolved by pull request',
    required=True,
)
def add_issue_url_to_pr(repo, pull_request_number, issue_key):
    jira_url = "https://rpc-openstack.atlassian.net/browse/"
    pull_request = repo.pull_request(pull_request_number)
    current_body = pull_request.body or ""

    issue_text = "Issue: [{key}]({url}{key})".format(
        url=jira_url,
        key=issue_key,
    )

    if issue_text in current_body:
        click.echo(
            "Pull request not updated, it already includes issue reference."
        )
    else:
        if current_body:
            updated_body = "{body}\n\n{issue}".format(
                body=current_body,
                issue=issue_text,
            )
        else:
            updated_body = issue_text

        success = pull_request.update(body=updated_body)
        if success:
            click.echo("Pull request updated with issue reference.")
        else:
            raise Exception("There was a failure updating the pull request.")


def branch_api_request(repo, branch, method, postfix="", data=None):
    """Make Requests to the github branch protection api.

    Not supported by github3.py yet (6th September 2017)
    """
    url = "{branch_url}/protection{postfix}".format(
        branch_url=repo.branches_urlt.expand(branch=branch),
        postfix=postfix
    )
    # Branch protection api is in preview and requires a specific content type
    response = repo._session.request(
        method, url,
        headers={'Accept': 'application/vnd.github.loki-preview+json'},
        data=data)
    return response


@cli.command()
@click.pass_context
@click.option(
    '--mainline',
    required=True,
    help="Mainline branch to cut from"
)
@click.option(
    '--rc',
    required=True,
    help="Release Candidate branch (re)create"
)
def update_rc_branch(ctx, mainline, rc):
    """Update rc branch.

    1. Store branch protection data
    2. Delete rc branch
    3. Create rc branch from head of mainline
    4. Enable branch protection with skeleton or previously stored settings.

    return codes:
        0: OK
        1: Unknown Failures
        2: Usage Error
        5: RC branch without branch protection detected.
    """
    try:
        repo = ctx.obj
        return_code = 0
        branch_protection_enabled = False

        # check if branch exists
        if rc in (b.name for b in repo.iter_branches()):
            logger.debug("Branch {} exists".format(rc))
            # rc branch exists
            branch_protection_response = branch_api_request(repo, rc, 'GET')
            if branch_protection_response.status_code == 200:
                # rc branch exists and protection enabled
                logger.debug("Branch {} has protection enabled".format(rc))
                branch_protection_enabled = True
                # disable branch protection
                r = branch_api_request(repo, rc, 'DELETE')
                r.raise_for_status()
                logger.debug("Branch protection disabled")
            elif branch_protection_response.status_code == 404:
                # rc branch exists without protection
                # set a return_code so that jenkins can notify the RE team
                # of a branch protection violation.
                return_code = 5
                print ("Warning: Branch: {} exists but does not have"
                       " branch protection enabled.".format(rc))
            else:
                # failure retrieving branch protection status
                branch_protection_response.raise_for_status()

            # Delete branch
            r = repo._session.request(
                'DELETE',
                repo.git_refs_urlt.expand(sha="heads/{}".format(rc)))
            r.raise_for_status()
            logger.debug("Branch {} deleted".format(rc))

        mainline_sha = repo.branch(mainline).commit.sha
        logger.debug("Mainline SHA: {}".format(mainline_sha))

        # create rc branch pointing at head of mainline
        repo.create_ref("refs/heads/{}".format(rc), mainline_sha)
        logger.debug("Branch {} created".format(rc))

        # Skeleton branch protection data, used to protect a new branch.
        protection_data = {
            "required_status_checks": None,
            "enforce_admins": True,
            "required_pull_request_reviews": {
                "dismissal_restrictions": {},
                "dismiss_stale_reviews": False,
                "require_code_owner_reviews": False
            },
            "restrictions": None
        }

        # Incorporate previous branch protection data if the branch was
        # protected perviously
        if branch_protection_enabled:
            stored_bpd = branch_protection_response.json()
            protection_data.update(stored_bpd)
            # The github api returns enforce_admins as dict, but requires it to
            # be sent as a bool.
            protection_data['enforce_admins'] \
                = stored_bpd['enforce_admins']['enabled']

        # Enable branch protection
        r = branch_api_request(repo, rc, 'PUT',
                               data=json.dumps(protection_data))
        r.raise_for_status()
        logger.debug("Branch Protection enabled for branch {}".format(rc))

        # Ensure the rc branch was not updated to anything else while it was
        # unprotected. Stored mainline_sha is used incase mainline has
        # moved on since the SHA was acquired.
        assert mainline_sha == repo.branch(rc).commit.sha
        logger.debug("rc branch update complete")
    except Exception as e:
        if return_code == 0:
            return_code = 1
        print "Failure Resetting RC branch: {}".format(e)
    finally:
        ctx.exit(return_code)


@cli.command()
@click.pass_obj
@click.option(
    '--version',
    required=True,
    help="version to release"
)
@click.option(
    '--ref',
    required=True,
    help="Reference to create release from (branch, SHA etc)"
)
@click.option(
    '--body',
    required=True,
    type=click.File('r'),
    help="File containing release message body"
)
def create_release(repo, version, ref, body):
    try:
        repo.create_release(
            version,            # tag name
            ref,                # tag reference
            version,            # release name
            body.read()         # release body
        )
        print "Release {} created.".format(version)
    except github3.models.GitHubError as e:
        print "Error creating release: {}".format(e)
        if e.code == 422:
            print "Failed to create release, tag already exists?"
            raise SystemExit(5)
        if e.code == 404:
            print "Failed to create release, Jenkins lacks repo perms?"
            raise SystemExit(6)
        else:
            raise e


if __name__ == "__main__":
    cli()
