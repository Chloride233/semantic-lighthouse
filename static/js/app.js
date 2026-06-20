import { route, initRouter, navigate } from './router.js';
import { initNavbar } from './components/navbar.js';
import { state, setState, restoreGroupContext } from './state.js';
import { api } from './api.js';

import { render as authPage } from './pages/auth.js';
import { render as onboardingPage } from './pages/onboarding.js';
import { render as askPage } from './pages/ask.js';
import { render as groupsPage } from './pages/groups.js';
import { render as documentsPage } from './pages/documents.js';
import { render as jobsPage } from './pages/jobs.js';
import { render as ragPage } from './pages/rag.js';
import { render as conversationsPage } from './pages/conversations.js';
import { render as tasksPage } from './pages/tasks.js';
import { render as agentPage } from './pages/agent.js';
import { render as ontologyPage } from './pages/ontology.js';
import { render as projectsPage } from './pages/projects.js';
import { render as projectPage } from './pages/project.js';

route('/login', authPage);
route('/onboarding', onboardingPage);
route('/ask', askPage);
route('/groups', groupsPage);
route('/groups/:gid/projects', projectsPage);
route('/groups/:gid/projects/:pid', projectPage);
route('/groups/:gid/documents', documentsPage);
route('/groups/:gid/jobs', jobsPage);
route('/groups/:gid/rag', ragPage);
route('/groups/:gid/conversations', conversationsPage);
route('/groups/:gid/tasks', tasksPage);
route('/groups/:gid/agent', agentPage);
route('/groups/:gid/ontology', ontologyPage);

initNavbar('navbar');

(async function start() {
  await bootstrap();
  initRouter('outlet');
})();

async function bootstrap() {
  if (!state.accessToken) return;
  try {
    const me = await api('/auth/me');
    const groups = me.groups || [];
    restoreGroupContext(groups);
    setState({ currentUser: me, groups });
  } catch (_) {
    // 401 will redirect to login via router
  }

  // Default landing: authenticated with group → Pilot; without group → 工作区
  const hash = location.hash.replace('#', '') || '';
  if (!hash || hash === '/') {
    if (state.currentGroupId) {
      navigate(`/groups/${state.currentGroupId}/projects`);
    } else if ((state.groups || []).length > 0) {
      navigate(`/groups/${state.groups[0].group_id}/projects`);
    } else {
      navigate('/groups');
    }
  }
}
