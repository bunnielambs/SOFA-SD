// Contas de usuario (Netlify Identity, gratuito). So existe na versao online.
// Cada conta guarda em user_metadata: full_name e sofa = { favs, prefs }.
import { isHosted } from './api.js'

let lib = null
const L = async () => (lib ||= await import('@netlify/identity'))
export const authAvailable = isHosted

const MSG = [
  [/invalid.*(login|credential|grant)|email or password/i, 'E-mail ou senha incorretos.'],
  [/not confirmed|confirm your email|email not confirmed/i, 'Confirme seu e-mail antes de entrar: abra o link que chegou na sua caixa de entrada.'],
  [/already.*registered|already exists|already been registered/i, 'Já existe uma conta com esse e-mail. Use "Entrar" ou "Esqueci a senha".'],
  [/password.*(short|least|weak)/i, 'A senha precisa ter pelo menos 8 caracteres.'],
  [/signup.*disabled/i, 'O cadastro está fechado no momento.'],
  [/rate limit|too many/i, 'Muitas tentativas seguidas. Espere alguns minutos e tente de novo.'],
  [/identity.*(not|missing)|MissingIdentity/i, 'O login ainda não foi ativado no site. Avise quem administra o SOFA SD.'],
  [/not found|\b404\b/i, 'O login ainda não foi ativado no site. Avise quem administra o SOFA SD.'],
  [/network|fetch|failed to fetch/i, 'Sem conexão. Confira a internet e tente de novo.'],
]
export function authError(e) {
  const t = `${e?.name || ''} ${e?.message || e || ''}`
  for (const [re, m] of MSG) if (re.test(t)) return m
  return 'Não foi possível concluir agora (' + (e?.message || 'erro desconhecido') + ').'
}

export async function initAuth() {
  if (!authAvailable) return { user: null }
  const l = await L(); let callback = null, callbackError = null
  try { callback = await l.handleAuthCallback() } catch (e) { callbackError = authError(e) }
  let user = null
  try { user = await l.getUser() } catch (e) {}
  return { user, callback, callbackError }
}
export async function onAuth(cb) { if (!authAvailable) return () => {}; const l = await L(); return l.onAuthChange((ev, user) => cb(ev, user)) }
export async function signIn(email, password) { const l = await L(); return l.login(email.trim(), password) }
export async function signUp(name, email, password) { const l = await L(); return l.signup(email.trim(), password, { full_name: name.trim() }) }
export async function signOut() { const l = await L(); return l.logout() }
export async function forgot(email) { const l = await L(); return l.requestPasswordRecovery(email.trim()) }
export async function newPassword(password) { const l = await L(); return l.updateUser({ password }) }
export async function saveProfile(data) { const l = await L(); return l.updateUser({ data }) }
export const userName = u => u?.userMetadata?.full_name || u?.name || ''
export const userSofa = u => u?.userMetadata?.sofa || null
