// Constantes puras compartidas por la vista Overview y sus futuros modales.
// Todo lo que hay aquí no tiene reactividad ni side effects.

export const SCAN_MESSAGES = [
  'DETECTANDO TEJIDOS CANCERÍGENOS...',
  'MIDIENDO NIVEL DE TILT EN SANGRE...',
  'CALIBRANDO RADIÁMETRO DE KDA...',
  'INDEXANDO TROLLS EN BASE DE DATOS...',
  'DESCARGANDO VERGÜENZA AJENA...',
  'ANALIZANDO PATRONES DE FEED...',
  'BUSCANDO YASUOS 0/10 EN MATCH HISTORY...',
  'CARGANDO EXCUSAS PREDETERMINADAS...',
  'VERIFICANDO INTEGRIDAD DEL JUNGLER...',
  'COMPUTANDO DAÑO NO INFLIGIDO...',
  'ESCANEANDO CHAT POR /ALL ENEMY...',
  'DETECTANDO PING DE 9999 MS...',
  'REVISANDO STREAM DE CEREZA FURIOSA...',
  'CONTANDO MUERTES EN TOWER DIVE...',
  'IDENTIFICANDO BUILDS DE SOLO AP SOBRE AD...',
]

export const LOADING_FLAVORS = [
  'Abriendo la tumba de partidas perdidas...',
  'Convenciendo a Riot de que respondan...',
  'Extrayendo feed del jungla...',
  'Filtrando excusas de tus aliados...',
  'Pidiéndole perdón a Riot por spammear la API...',
  'Detectando si era tu culpa (spoiler: sí)...',
  'Rescatando KDA de la papelera de reciclaje...',
  'Traduciendo flame del all chat al español...',
  'Consultando a Baron Nashor...',
  'Buscando el botón de "no jugar con randoms"...',
  'Revisando si había Yasuo en tu team...',
  'Cargando más tumores que el Chernobyl...',
  'Pagando el ping con nuestras lágrimas...',
  'Reconstruyendo el muro que te comió en mid...',
]

export const EXCUSE_STARTERS = [
  'Perdí porque',
  'No fue mi culpa,',
  'La realidad es que',
  'Obviamente',
  'Claramente',
]

export const EXCUSE_REASONS = [
  'el jungla estaba AFK en el bush',
  'mi support era un Teemo con Sunfire',
  'había lag del servidor (1200 ms fijos)',
  'mi ADC pusheaba la 1 con 30 de HP',
  'el mid hizo full AP sobre un Garen',
  'el top feedeó 0/7 antes del minuto 10',
  'mi duo me flameó por invocar Ignite',
  'Riot nerfeó a mi champ en parche no anunciado',
  'había un smurf en el enemy team',
  'mi internet se cayó justo en teamfight',
  'el jungla no gankeó ni una vez',
  'el support se olvidó las wards en casa',
  'el chat de mi team estaba en ruso',
  'mi compañero se comió el blue sin pedir permiso',
  'el enemigo tenía un Yasuo inmortal',
  'nadie respondió a mis ? pings en baron',
  'mi team pickeó 5 AD contra 3 tanques',
  'el jungla me hizo counterjungle a MI jungla',
  'mi mouse se desconectó',
  'Cereza Furiosa tilteó en el minuto 2',
]

export const EXCUSE_ENDINGS = [
  'y además hacía mucho calor.',
  'era imposible ganar.',
  'y los dioses no me querían.',
  'así cualquiera pierde.',
  'y por eso bajé de elo.',
  'pero bueno, GG WP.',
  'y yo era el único intentándolo.',
  '— no tenía sentido insistir.',
]

// Rune styles (Riot IDs 8000-8400)
export const RUNE_STYLES: Record<number, { name: string, color: string }> = {
  8000: { name: 'Precision',   color: '#c89b3c' },
  8100: { name: 'Domination',  color: '#dc2626' },
  8200: { name: 'Sorcery',     color: '#a855f7' },
  8300: { name: 'Inspiration', color: '#06b6d4' },
  8400: { name: 'Resolve',     color: '#22c55e' },
}

// Summoner spells por Riot spell ID → nombre DDragon.
export const SUMMONER_SPELLS: Record<number, string> = {
  1: 'SummonerBoost',
  3: 'SummonerExhaust',
  4: 'SummonerFlash',
  6: 'SummonerHaste',
  7: 'SummonerHeal',
  11: 'SummonerSmite',
  12: 'SummonerTeleport',
  13: 'SummonerMana',
  14: 'SummonerDot',
  21: 'SummonerBarrier',
  32: 'SummonerSnowball',
}

export const ROLE_ORDER = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
export const ROLE_LABEL: Record<string, string> = {
  TOP: 'TOP', JUNGLE: 'JNG', MIDDLE: 'MID', BOTTOM: 'ADC', UTILITY: 'SUP',
}

export const TIER_COLORS: Record<string, string> = {
  IRON: 'text-[#8a7462]', BRONZE: 'text-[#a0522d]', SILVER: 'text-[#a0a9b0]',
  GOLD: 'text-[#c89b3c]', PLATINUM: 'text-[#4e9e8a]', EMERALD: 'text-[#2ecc71]',
  DIAMOND: 'text-[#7ec8e3]', MASTER: 'text-[#c45cff]', GRANDMASTER: 'text-[#ff4444]',
  CHALLENGER: 'text-[#f4c542]', UNRANKED: 'text-white/40',
}

export const tumorColor = (score: number): string => {
  if (score >= 75) return 'text-red-500'
  if (score >= 50) return 'text-orange-400'
  if (score >= 25) return 'text-yellow-400'
  return 'text-green-400'
}

export const tumorLabel = (score: number): string => {
  if (score >= 75) return '☢ NUCLEAR'
  if (score >= 50) return '☣ TUMOR'
  if (score >= 25) return '⚠ SUS'
  return '✓ DECENTE'
}
