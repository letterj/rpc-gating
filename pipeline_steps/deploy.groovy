def deploy(){
  common.conditionalStep(
    step_name: "Deploy",
    step: {
      List playbooks = common._parse_json_string(json_text: env.PLAYBOOKS)
      print(playbooks)
      print(playbooks.size())
      for (def i=0; i<playbooks.size(); i++){
        String playbook = playbooks[i]
        print(playbook)
        stage(playbook.playbook){
          common.openstack_ansible(playbook)
        } //stage
      } // for
    } //  step
  ) //conditionalStep
}

def deploy_sh(Map args) {
  common.conditionalStage(
    stage_name: "Deploy RPC w/ Script",
    stage: {
      List environment_vars = args.environment_vars \
                              + common.get_deploy_script_env()
      withCredentials([
        string(
          credentialsId: "INFLUX_IP",
          variable: "INFLUX_IP"
        )
      ]){
        withEnv(environment_vars) {
          ansiColor('xterm') {
            dir("/opt/rpc-openstack/") {
              sh """#!/bin/bash
              scripts/deploy.sh
              """
            } // dir
          } // ansiColor
        } // withEnv
      } //withCredentials
    } // stage
  ) // conditionalStage
}

def upgrade(String stage_name, String upgrade_script, List env_vars,
            String branch = "auto", String dest = "/opt") {
  common.conditionalStage(
    stage_name: stage_name,
    stage: {
      List environment_vars = env_vars + common.get_deploy_script_env()
      withEnv(environment_vars){
        dir("/opt/rpc-openstack/openstack-ansible"){
          sh "git reset --hard"
        }
        common.prepareRpcGit(branch, dest)
        withCredentials([
          string(
            credentialsId: "INFLUX_IP",
            variable: "INFLUX_IP"
          )
        ]){
          dir("/opt/rpc-openstack"){
            sh """
              scripts/$upgrade_script
            """
          } // dir
        }
      } // withEnv
    } // stage
  ) // conditionalStage
}

def upgrade_minor(Map args) {
  upgrade("Minor Upgrade", "deploy.sh", args.environment_vars)
}

def upgrade_major(Map args) {
  // Required to run first for major upgrade resource generation
  tempest.tempest_install()
  upgrade("Major Upgrade", "test-upgrade.sh", args.environment_vars)
}

def upgrade_leapfrog(Map args) {
  // for a PR to kilo, we don't want to checkout the PR commit at this point
  // as it's already been used to deploy kilo.
  String branch = "auto"
  if (env.SERIES == "kilo" && env.TRIGGER == "pr"){
    branch="newton"
  }
  // Required to run first for leapfrog resource generation
  tempest.tempest_install()
  upgrade("Leapfrog Upgrade",
          "leapfrog/ubuntu14-leapfrog.sh",
          args.environment_vars,
          branch)

}

return this;
