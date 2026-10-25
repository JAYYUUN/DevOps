import groovy.json.JsonSlurper
import jenkins.model.Jenkins
import hudson.util.Secret
import hudson.model.StringParameterDefinition
import hudson.model.ParametersDefinitionProperty
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec
import com.dabsquared.gitlabjenkins.GitLabPushTrigger
import net.sf.json.JSONObject
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
ensureCredential(new UsernamePasswordCredentialsImpl(CredentialsScope.GLOBAL, cfg.registryCredentialId,
        marker + ' Registry push', cfg.registryUser, cfg.registryPassword))
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
    new StringParameterDefinition('CICD_GITOPS_CREDENTIAL', cfg.deploymentCredentialId, 'Scoped GitOps credential'),
    new StringParameterDefinition('CICD_REGISTRY', cfg.registryAddress, 'Registry host'),
    new StringParameterDefinition('CICD_IMAGE_REPOSITORY', cfg.registryRepository, 'Image path'),
    new StringParameterDefinition('CICD_REGISTRY_CREDENTIAL', cfg.registryCredentialId, 'Registry push credential'),
    new StringParameterDefinition('CICD_BUILD_CONTEXT', cfg.buildContext, 'Build context'),
    new StringParameterDefinition('CICD_DOCKERFILE', cfg.dockerfile, 'Dockerfile relative to repository'),
    new StringParameterDefinition('CICD_TEST_COMMAND', cfg.testCommand, 'Project test command')
]))
def triggers = []
if (cfg.webhookEnabled) {
    def options = JSONObject.fromObject([
        triggerOnPush: true, triggerOnMergeRequest: false, triggerOnAcceptedMergeRequest: false,
        triggerOnClosedMergeRequest: false, triggerOnNoteRequest: false, triggerOnPipelineEvent: false,
        triggerOnApprovedMergeRequest: false, triggerToBranchDeleteRequest: false,
        triggerOpenMergeRequestOnPush: 'never', branchFilterType: 'NameBasedFilter',
        includeBranchesSpec: cfg.branch, excludeBranchesSpec: '', secretToken: cfg.webhookSecret,
        noteRegex: '', skipWorkInProgressMergeRequest: true, ciSkip: true,
        setBuildDescription: false, addNoteOnMergeRequest: false, addCiMessage: false,
        addVoteOnMergeRequest: false, acceptMergeRequestOnSuccess: false,
        sourceBranchRegex: '', targetBranchRegex: '', labelsThatForcesBuildIfAdded: '',
        mergeRequestLabelFilterConfig: [include: '', exclude: ''], pendingBuildName: '',
        cancelPendingBuildsOnUpdate: false
    ])
    triggers.add(instance.getDescriptorOrDie(GitLabPushTrigger.class).newInstance(null, options))
}
job.addProperty(new PipelineTriggersJobProperty(triggers))
job.save()
println('CICD_SETUP_OK')
