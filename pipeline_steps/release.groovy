void tag(String version, String ref){
  print "Tagging ${version} at ${ref}"
  sshagent (credentials:['rpc-jenkins-svc-github-ssh-key']){
    sh """/bin/bash -xe
      git fetch --all --tags
      git tag -a -m \"${version}\" \"${version}\" origin/${ref}
      git push origin \"${version}\"
    """
  }
}

void update_rc_branch(String repo, String mainline, String rc){
  print "Resetting ${rc} to head of ${mainline}"
  sshagent (credentials:['rpc-jenkins-svc-github-ssh-key']){
    sh """/bin/bash -xe
      git fetch --all --tags
      git checkout -b ${rc} || git checkout ${rc}
      git reset --hard origin/${mainline}
      git push -f origin ${rc}:${rc}
    """
  }
}

return this
