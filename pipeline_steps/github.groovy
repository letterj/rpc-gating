
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

// Reset rc branch to head of mainline ready for the next development cycle
def update_rc_branch(
    String org="rcbops",
    String repo,
    String mainline,
    String rc){
  print "Resetting ${rc} to head of ${mainline}"
  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    Integer ret_code = sh (returnStatus: true, script: """#!/bin/bash -xe
      cd ${env.WORKSPACE}
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --debug \
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        update_rc_branch\
        --mainline '$mainline'\
        --rc '$rc'
    """)
    if (ret_code == 5){
      slackSend (
        channel: '#rpc-releng',
        color: 'warning',
        message: "Unprotected rc branch found: ${repo}/${rc}")
    }else if(ret_code != 0){
      throw new Exception("Failed to update rc branch ${repo}/${rc}."
                          +" Return Code: ${ret_code}")
    }
  }
}

// Create github release and tag
def create_release(
    String org="rcbops",
    String repo,
    String version,
    String ref,
    String reno_body_file){
  print "Creating github release ${version} for ${repo}@${ref}"
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
        --debug \
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        create_release\
        --version '$version'\
        --ref '$ref' \
        --body reno_body_file
      echo \$?
    """
  }
}

return this;
