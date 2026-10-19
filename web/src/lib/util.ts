// Funções puras (sem DOM nem rede), com o mesmo comportamento de static/js/util.js.

export const DESTINO_PANICO = "https://www.google.com/";

/** Milissegundos até `iso` (negativo se já passou). */
export function msAte(iso: string, agora = Date.now()): number {
  return Date.parse(iso) - agora;
}

/** Tempo restante legível: "4:05" (menos de 1 h), "23 h 05 min" (menos de 1 dia), "3 d 4 h". */
export function formatarRestante(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  if (s < 3600) return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  const min = Math.ceil(s / 60);
  if (min < 24 * 60) return `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;
  const horas = Math.floor(min / 60);
  return `${Math.floor(horas / 24)} d ${horas % 24} h`;
}

/** Nome de um prazo das mensagens (minutos depois da leitura; null = nunca). */
export function rotuloPrazo(minutos: number | null): string {
  if (minutos == null) return "nunca";
  if (minutos === 1440) return "24 horas";
  if (minutos === 20160) return "14 dias";
  const unidades: [number, string, string][] = [
    [43200, "mês", "meses"], [10080, "semana", "semanas"], [1440, "dia", "dias"], [60, "hora", "horas"], [1, "minuto", "minutos"],
  ];
  for (const [tamanho, um, varios] of unidades) {
    if (minutos % tamanho === 0) {
      const n = minutos / tamanho;
      return `${n} ${n === 1 ? um : varios}`;
    }
  }
  return `${minutos} minutos`;
}

export function descreverPrazo(minutos: number | null): string {
  return minutos == null
    ? "Nesta conversa, as mensagens não somem."
    : `As mensagens somem ${rotuloPrazo(minutos)} depois de lidas.`;
}

/** Paradas da barra de distância: passos pequenos perto, maiores longe; a última é "qualquer". */
export const PARADAS_DISTANCIA: (number | null)[] = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300, 500, null];

export function indiceDaDistancia(km: number | null): number {
  if (km == null) return PARADAS_DISTANCIA.length - 1;
  const i = PARADAS_DISTANCIA.findIndex((p) => p != null && p >= km);
  return i === -1 ? PARADAS_DISTANCIA.length - 2 : i;
}

export function distanciaDoIndice(i: number): number | null {
  const max = PARADAS_DISTANCIA.length - 1;
  return PARADAS_DISTANCIA[Math.min(max, Math.max(0, Math.round(Number(i)) || 0))];
}

export const rotuloDistancia = (km: number | null) => (km == null ? "Qualquer distância" : `Até ${km} km`);
export const descreverDistancia = (km: number | null | undefined) => (km == null ? null : `até ${km} km`);

/** Texto amigável a partir do corpo de erro do FastAPI. */
export function mensagemDeErro(dados: unknown): string {
  const corpo = dados as { detail?: unknown; requisicao?: string } | null;
  const d = corpo?.detail;
  if (typeof d === "string" && corpo?.requisicao) return `${d} (código ${corpo.requisicao})`;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) {
    return d.map((e: { msg?: unknown }) => String(e.msg).replace(/^Value error, /, "")).join(" · ");
  }
  return "Algo deu errado. Tente de novo.";
}

export const dataCurta = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "nunca");
export const dataHora = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

/** Hora relativa curta para listas: "agora", "12 min", "3 h", "ontem", "12/05". */
export function quandoRelativo(iso: string | null, agora = Date.now()): string {
  if (!iso) return "";
  const min = Math.floor((agora - Date.parse(iso)) / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `${min} min`;
  if (min < 24 * 60) return `${Math.floor(min / 60)} h`;
  if (min < 48 * 60) return "ontem";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export const iniciais = (nome: string) =>
  nome.trim().split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase() ?? "").join("") || "?";

/** Valor para <input type="datetime-local"> no fuso do aparelho. */
export function paraCampoDataHora(data: Date): string {
  const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export const juntarClasses = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(" ");

// Categorias do catálogo (db/seed.sql) chegam como slug; aqui ganham o nome para exibir.
const CATEGORIAS: Record<string, string> = {
  restricao: "Restrição", estetica: "Estética", verbal: "Verbal", sensacao: "Sensação",
  dinamica: "Dinâmica", exposicao: "Exposição", fetiche: "Fetiche",
};
export const nomeDaCategoria = (c: string | null) =>
  !c ? "Outros" : CATEGORIAS[c] ?? c.charAt(0).toUpperCase() + c.slice(1).replace(/-/g, " ");
