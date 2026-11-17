import { getStore } from "@netlify/blobs"

export const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } })

export const cache = () => getStore("sofa-cache")

export async function readCache(key) {
  try { return await cache().get(key, { type: "json" }) } catch (e) { return null }
}
export async function writeCache(key, value) {
  try { await cache().setJSON(key, value) } catch (e) { /* cache e opcional */ }
}

// Mensagens legiveis para os erros das fontes
export function sourceError(status) {
  if (status === 429) return "limite de requisições da fonte atingido (HTTP 429)"
  if (status === 401 || status === 403) return `acesso negado pela fonte (HTTP ${status}): chave inválida ou dado fora do plano gratuito`
  if (status === 404) return "recurso não encontrado na fonte (HTTP 404)"
  return `erro da fonte (HTTP ${status})`
}
