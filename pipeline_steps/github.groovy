
def create_issue(
    String tag,
    String link,
    String label="jenkins-build-failure",
    String org="rcbops",
    String repo="u-suk-dev"){
  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd ${env.WORKSPACE}
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        create_issue\
        --tag '$tag'\
        --link '$link'\
        --label '$label'
    """
  }
}

/**
 * Add issue link to pull request description
 *
 * Pull request commit messages include the issue key for an issue on Jira.
 * Update the description of the current GitHub pull request with a link to
 * the Jira issue.
 */
void add_issue_url_to_pr(String upstream="upstream"){
  List org_repo = env.ghprbGhRepository.split("/")
  String org = org_repo[0]
  String repo = org_repo[1]

  Integer pull_request_number = env.ghprbPullId as Integer

  dir(repo) {
    git branch: env.ghprbSourceBranch, url: env.ghprbAuthorRepoGitUrl
    sh """#!/bin/bash
      set -x
      git remote add ${upstream} https://github.com/${org}/${repo}.git
      git remote update
    """
  }
  String issue_key = common.get_jira_issue_key(repo)

  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd $env.WORKSPACE
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        add_issue_url_to_pr\
        --pull-request-number '$pull_request_number'\
        --issue-key '$issue_key'
    """
  }
  return null
}

/* Toggle whether admins can override branch protection
This is used to allow jenkins to force push when
resetting rc branches
state = "True" (enabled)
      or "False" (disabled)
*/
def set_branch_protection_admin_enforcement(
    String org="rcbops",
    String repo,
    String branch,
    String state){
  print "Setting branch protection admin enforcement to ${state} for ${org}/${repo}/${branch}"
  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd ${env.WORKSPACE}
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        set_admin_enforcement\
        --branch '$branch'\
        --admin-enforcement-enabled '$state'
    """
  }
}


return this;
