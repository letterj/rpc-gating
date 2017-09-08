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

return this
