import groovy.json.JsonSlurper
import jenkins.model.Jenkins
import hudson.util.Secret
import hudson.model.StringParameterDefinition
import hudson.model.ParametersDefinitionProperty
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec
import hudson.triggers.SCMTrigger
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.domains.Domain
import com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl

def cfg = new JsonSlurper().parseText(new String('__CICD_DATA__'.decodeBase64(), 'UTF-8'))
def marker = '[cicd-integration:' + cfg.owner + ']'
def instance = Jenkins.get()
def existing = instance.getItemByFullName(cfg.job)
if (existing != null && (!(existing instanceof WorkflowJob) || !(existing.description ?: '').contains(marker))) {
    throw new IllegalStateException('같은 이름의 기존 비관리 작업이 있습니다')
}
def store = SystemCredentialsProvider.getInstance().getStore()
def domain = Domain.global()
def ensureCredential = { credential ->
    def old = store.getCredentials(domain).find { it.id == credential.id }
    if (old != null) {
        if (!(old.description ?: '').contains(marker)) {
            throw new IllegalStateException('같은 ID의 기존 비관리 인증정보가 있습니다')
        }
        store.updateCredentials(domain, old, credential)
    } else {
        store.addCredentials(domain, credential)
    }
}
ensureCredential(new UsernamePasswordCredentialsImpl(CredentialsScope.GLOBAL, cfg.sourceCredentialId,
        marker + ' source read', cfg.sourceUser, cfg.sourceToken))
ensureCredential(new StringCredentialsImpl(CredentialsScope.GLOBAL, cfg.deploymentCredentialId,
        marker + ' GitOps write', Secret.fromString(cfg.deploymentToken)))
def job = existing ?: instance.createProject(WorkflowJob, cfg.job)
job.description = marker + ' GitLab → Jenkins → GitOps → Argo CD'
def scm = new GitSCM([new UserRemoteConfig(cfg.sourceUrl, null, cfg.sourceCredentialId)],
        [new BranchSpec('*/' + cfg.branch)], false, [], null, null, [])
def definition = new CpsScmFlowDefinition(scm, cfg.pipelineFile)
definition.lightweight = true
job.definition = definition
job.addProperty(new ParametersDefinitionProperty([
    new StringParameterDefinition('CICD_GITLAB_API', cfg.api, 'GitLab API'),
    new StringParameterDefinition('CICD_SOURCE_PROJECT_ID', cfg.sourceProjectId.toString(), 'Source project'),
    new StringParameterDefinition('CICD_GITOPS_PROJECT_ID', cfg.deploymentProjectId.toString(), 'GitOps project'),
    new StringParameterDefinition('CICD_GITOPS_BRANCH', cfg.deploymentBranch, 'GitOps branch'),
    new StringParameterDefinition('CICD_MANIFEST_PATH', cfg.manifestPath, 'Example manifest'),
    new StringParameterDefinition('CICD_GITOPS_CREDENTIAL', cfg.deploymentCredentialId, 'Scoped GitOps credential')
]))
job.addProperty(new PipelineTriggersJobProperty([new SCMTrigger(cfg.poll)]))
job.save()
println('CICD_SETUP_OK')
