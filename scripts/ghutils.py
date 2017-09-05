#!/usr/bin/env python

# This script contains github related utilties for Jenkins.


import click
import github3
import json


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
def cli(ctxt, org, repo, pat):
    gh = github3.login(token=pat)
    repo_ = gh.repository(org, repo)
    ctxt.obj = repo_


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


def branch_api_request(
        repo,
        branch,
        method,
        postfix="/enforce_admins"):
    """Make Requests to the github branch protection api
        Not supported by github3.py yet (6/9/2017)"""
    url = "{branch_url}/protection{postfix}".format(
        branch_url=repo.branches_urlt.expand(branch=branch),
        postfix=postfix
    )
    # Branch protection api is in preview and requires a specific content type
    response = repo._session.request(
        method, url,
        headers={'Accept': 'application/vnd.github.loki-preview+json'})
    return response


@cli.command()
@click.pass_context
@click.option(
    '--branch',
    required=True,
    help="Branch to set branch protection for."
)
@click.option(
    '--admin-enforcement-enabled',
    help="Enable or disable branch protection parameters for admins",
    type=click.Choice(["True", "False"]),
    required=True
)
def set_admin_enforcement(ctx, branch, admin_enforcement_enabled):
    repo = ctx.obj
    if admin_enforcement_enabled == "True":
        method = "POST"
    else:
        method = "DELETE"

    if ctx.invoke(get_branch_protection, branch=branch):
        print ("Setting branch protection admin"
               " encforcement to {} ".format(admin_enforcement_enabled))
        branch_api_request(repo, branch, method).raise_for_status()
        ctx.invoke(get_admin_enforcement, branch=branch)
    else:
        print ("Not modifying branch protection admin enforcement")


@cli.command()
@click.pass_obj
@click.option(
    '--branch',
    required=True,
    help="Branch to query"
)
def get_admin_enforcement(repo, branch):
    response = branch_api_request(repo, branch, 'GET')
    response.raise_for_status()
    print response.json()


@cli.command()
@click.pass_obj
@click.option(
    '--branch',
    required=True,
    help="Branch to query"
)
def get_branch_protection(repo, branch):
    response = branch_api_request(repo, branch, 'GET', postfix="")
    if response.status_code == 200:
        print "Branch Protection Enabled"
        print json.dumps(response.json(), indent=4)
        return True
    else:
        print "Branch Protection Disabled"
        return False


if __name__ == "__main__":
    cli()
