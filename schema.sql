-- ============================================================
-- Tabela: respostas_fitzpatrick
-- Armazena as respostas do questionário + resultado da IA
-- coletados na página "Retrato Brasileiro".
-- ============================================================

-- gen_random_uuid() requer a extensão pgcrypto (já habilitada
-- por padrão na maioria dos projetos Supabase).
create extension if not exists pgcrypto;

create table if not exists public.respostas_fitzpatrick (
  id                   uuid primary key default gen_random_uuid(),
  data_envio           timestamptz not null default now(),
  fototipo_questionario text not null,
  fototipo_ia          text not null,
  confianca_ia         float,
  avaliacao_usuario    text,
  probabilidades_json  jsonb,

  -- Validações leves de integridade dos dados
  constraint fototipo_questionario_valido
    check (fototipo_questionario in ('Tipo 1','Tipo 2','Tipo 3','Tipo 4','Tipo 5','Tipo 6')),
  constraint fototipo_ia_valido
    check (fototipo_ia in ('Tipo 1','Tipo 2','Tipo 3','Tipo 4','Tipo 5','Tipo 6')),
  constraint avaliacao_usuario_valida
    check (avaliacao_usuario is null or avaliacao_usuario in ('sim','parcialmente','nao')),
  constraint confianca_ia_faixa
    check (confianca_ia is null or (confianca_ia >= 0 and confianca_ia <= 100))
);

-- Índice para consultas por data (ex.: exportar respostas de um período)
create index if not exists idx_respostas_fitzpatrick_data_envio
  on public.respostas_fitzpatrick (data_envio desc);

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================
-- A tabela recebe envios de usuários anônimos (não autenticados)
-- vindos diretamente do navegador. A política abaixo permite
-- APENAS inserção pública, sem permitir leitura, alteração ou
-- exclusão via chave anônima — isso evita que qualquer visitante
-- veja ou manipule as respostas de outros participantes.
alter table public.respostas_fitzpatrick enable row level security;

create policy "Permitir insercao publica de respostas"
  on public.respostas_fitzpatrick
  for insert
  to anon
  with check (true);

-- Leitura/exportação dos dados deve ser feita pelo painel do
-- Supabase (autenticado como owner do projeto) ou por uma role
-- de serviço (service_role) usada apenas no backend/servidor,
-- nunca exposta no frontend.
