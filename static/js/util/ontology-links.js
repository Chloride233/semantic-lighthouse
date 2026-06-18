/** Ontology entity index for evidence-to-ontology bridge.
 *
 * Provides a cached lookup of ontology entities by document_id
 * or normalized source_path, so RAG citations and task sources
 * can link to ontology entities without new API calls per item.
 *
 * Read-only bridge: does NOT modify entities, relations, or KB.
 */

import { api } from '../api.js';

const cache = new Map();

/**
 * Load or return cached ontology entity index for a group.
 * Returns { byDocumentId: Map, bySourcePath: Map, entities: [] } or null on failure.
 */
export async function loadOntologyEntityIndex(gid) {
  if (!gid) return null;
  if (cache.has(gid)) return cache.get(gid);

  try {
    const data = await api(`/groups/${gid}/ontology/entities?limit=100`);
    const entities = data.entities || [];
    const byDocumentId = new Map();
    const bySourcePath = new Map();

    for (const e of entities) {
      if (e.document_id) byDocumentId.set(e.document_id, e);
      const sp = normalize(e.source_path || '');
      if (sp) {
        if (!bySourcePath.has(sp)) bySourcePath.set(sp, e);
        if (!sp.endsWith('.md')) bySourcePath.set(sp + '.md', e);
      }
    }

    const index = { byDocumentId, bySourcePath, entities };
    cache.set(gid, index);
    return index;
  } catch (_) {
    return null;
  }
}

/** Clear cached index for a group. */
export function clearOntologyEntityCache(gid) {
  cache.delete(gid);
}

/**
 * Look up ontology entity for a citation.
 * citation: { document_id, source_path }
 * index: from loadOntologyEntityIndex
 * Returns entity object or null.
 */
export function findEntityForCitation(citation, index) {
  if (!index || !citation) return null;
  if (citation.document_id && index.byDocumentId.has(citation.document_id)) {
    return index.byDocumentId.get(citation.document_id);
  }
  const sp = normalize(citation.source_path || '');
  if (sp) {
    if (index.bySourcePath.has(sp)) return index.bySourcePath.get(sp);
    if (!sp.endsWith('.md') && index.bySourcePath.has(sp + '.md')) return index.bySourcePath.get(sp + '.md');
  }
  return null;
}

function normalize(sp) {
  if (!sp) return '';
  let s = sp.replace(/\\/g, '/');
  if (s.startsWith('upload:')) s = s.slice(7);
  return s;
}
