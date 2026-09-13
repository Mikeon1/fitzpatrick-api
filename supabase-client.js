// ============================================================
// supabase-client.js
// Integração com o Supabase para salvar as respostas do
// questionário + resultado da IA da página "Retrato Brasileiro".
//
// Uso no HTML (módulo ES nativo, sem necessidade de bundler):
//   <script type="module" src="supabase-client.js"></script>
//
// Este arquivo expõe a função `enviarRespostaFitzpatrick` em
// `window`, para ser chamada a partir do script principal da
// página (veja o botão "Enviar avaliação" em index.html).
// ============================================================

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

// ------------------------------------------------------------
// Configuração
// ------------------------------------------------------------
// Substitua pelos valores do seu projeto Supabase
// (Project Settings -> API). A "anon key" é pública por design
// e segura para uso no frontend, DESDE QUE a tabela tenha Row
// Level Security habilitada (ver schema.sql) restringindo o que
// essa chave pode fazer — neste caso, apenas inserir registros.
const SUPABASE_URL = "https://rbmysunolucwzkdyvlgm.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJibXlzdW5vbHVjd3prZHl2bGdtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkzMTA0ODMsImV4cCI6MjEwNDg4NjQ4M30.5_A0NYqpg8e2cA21lJY7Y_-w-12zQUq7p3-2U3DXSIA";

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ------------------------------------------------------------
// Inserção de um novo registro
// ------------------------------------------------------------
/**
 * Envia uma resposta concluída para a tabela `respostas_fitzpatrick`.
 *
 * @param {Object} payload
 * @param {string} payload.fototipo_questionario  Ex: "Tipo 3"
 * @param {string} payload.fototipo_ia            Ex: "Tipo 4"
 * @param {number} payload.confianca_ia           Ex: 85.5 (0 a 100)
 * @param {string|null} payload.avaliacao_usuario "sim" | "parcialmente" | "nao" | null
 * @param {Object} payload.probabilidades_json    Ex: { "Tipo 1": 5.0, "Tipo 2": 85.5, ... }
 * @returns {Promise<{ data: object|null, error: object|null }>}
 */
async function enviarRespostaFitzpatrick(payload) {
  const registro = {
    fototipo_questionario: payload.fototipo_questionario,
    fototipo_ia: payload.fototipo_ia,
    confianca_ia: payload.confianca_ia ?? null,
    avaliacao_usuario: payload.avaliacao_usuario ?? null,
    probabilidades_json: payload.probabilidades_json ?? null,
  };

  const { data, error } = await supabase
    .from("respostas_fitzpatrick")
    .insert(registro)
    .select()
    .single();

  if (error) {
    console.error("Erro ao salvar resposta no Supabase:", error.message);
    return { data: null, error };
  }

  console.log("Resposta salva com sucesso:", data.id);
  return { data, error: null };
}

// Expostas globalmente para uso pelo script inline de index.html
window.enviarRespostaFitzpatrick = enviarRespostaFitzpatrick;

