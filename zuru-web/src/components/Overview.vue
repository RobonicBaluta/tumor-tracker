<template>
  <div class="flex-1 flex flex-col overflow-y-auto relative"
    :style="{ background: `linear-gradient(to bottom right, ${theme.from}, ${theme.to})` }">

    <!-- X-Ray scanning overlay -->
    <Transition name="xray">
      <div v-if="scanning" class="xray-overlay absolute inset-0 z-50 flex flex-col items-center justify-center overflow-hidden">
        <div class="xray-noise"></div>
        <div class="xray-scanlines"></div>
        <div class="scan-line"></div>
        <div class="scan-line-glow"></div>
        <!-- Floating particles -->
        <div v-for="i in 24" :key="`pt${i}`" class="xray-particle"
          :style="{
            left: `${(i * 37) % 100}%`,
            animationDelay: `${(i * 0.13) % 2}s`,
            animationDuration: `${3 + (i % 4)}s`
          }"></div>

        <div class="relative z-10 text-center select-none px-8">
          <p class="xray-label text-xs font-mono mb-6 tracking-[0.4em] text-cyan-300/60">HOSPITAL ZURUWEB · ONCOLOGÍA</p>
          <p class="xray-title glitch font-mono text-3xl font-bold tracking-widest text-white mb-2" data-text="ESCANEANDO">ESCANEANDO</p>
          <p class="xray-name font-mono text-cyan-400 text-xl tracking-widest mb-8">
            {{ formData.gameName || summoner.split('#')[0] }}<span class="text-cyan-300/50">#{{ formData.tagLine || summoner.split('#')[1] }}</span>
          </p>
          <div class="flex gap-2 justify-center">
            <span v-for="i in 3" :key="i" class="xray-dot" :style="{ animationDelay: `${(i - 1) * 0.3}s` }"></span>
          </div>
          <p class="xray-label text-[11px] font-mono mt-8 tracking-[0.2em] text-cyan-300/60 min-h-[16px] transition-opacity" :key="scanMessage">
            {{ scanMessage }}
          </p>
        </div>

        <!-- Corner marks (medical/film style) -->
        <div class="corner corner-tl"></div>
        <div class="corner corner-tr"></div>
        <div class="corner corner-bl"></div>
        <div class="corner corner-br"></div>
      </div>
    </Transition>

    <!-- Login screen -->
    <div v-if="!summoner" class="flex-1 flex justify-center items-center p-8">
      <div class="w-full max-w-md">
        <div class="bg-black/30 backdrop-blur-md p-12 rounded-2xl text-center shadow-2xl mb-6 animate-fade">
          <h1 class="text-white font-mono text-5xl mb-2">Top Tumores</h1>
          <div class="h-[3px] w-[60%] mx-auto my-5 bg-gradient-to-r from-transparent via-[#c89b3c] to-transparent"></div>
          <p class="text-white/50 text-base">Revisa el historial de tus peores compañeros</p>
        </div>

        <div class="bg-black/30 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade">
          <form @submit.prevent="login" class="space-y-5">
            <div>
              <label class="block text-[#c89b3c] text-sm font-semibold mb-2 font-mono">Nombre del Invocador</label>
              <input v-model="formData.gameName" type="text" placeholder="GameName"
                class="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-[#c89b3c] transition" required />
            </div>
            <div>
              <label class="block text-[#c89b3c] text-sm font-semibold mb-2 font-mono">Tag</label>
              <input v-model="formData.tagLine" type="text" placeholder="EUW"
                class="w-32 px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-[#c89b3c] transition" required />
            </div>
            <button type="submit" :disabled="loading"
              class="w-full bg-[#c89b3c] hover:bg-[#e0b84e] disabled:opacity-40 disabled:cursor-not-allowed text-black font-bold py-3 rounded-lg transition transform hover:scale-105 font-mono">
              Escanear tumores ☢️
            </button>
            <div v-if="error" class="bg-red-500/20 border border-red-500 text-red-300 px-4 py-3 rounded-lg text-sm">
              {{ error }}
            </div>
          </form>
        </div>

        <!-- Saved accounts -->
        <div v-if="savedAccounts.length" class="mt-4 animate-fade">
          <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2 text-center">MIS CUENTAS</p>
          <div class="flex flex-wrap gap-2 justify-center">
            <button v-for="entry in savedAccounts" :key="entry" @click="loadRecent(entry)"
              class="flex items-center gap-1.5 px-3 py-1.5 bg-[#c89b3c]/10 hover:bg-[#c89b3c]/20 border border-[#c89b3c]/30 hover:border-[#c89b3c]/60 text-[#c89b3c] hover:text-[#e0b84e] text-xs font-mono rounded-lg transition">
              ⭐ {{ entry }}
            </button>
          </div>
        </div>

        <!-- Recent searches -->
        <div v-if="recentSummoners.length" class="mt-4 animate-fade">
          <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2 text-center">BÚSQUEDAS RECIENTES</p>
          <div class="flex flex-wrap gap-2 justify-center">
            <button v-for="entry in recentSummoners" :key="entry" @click="loadRecent(entry)"
              class="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/15 hover:border-[#c89b3c]/50 text-white/70 hover:text-white text-xs font-mono rounded-lg transition">
              {{ entry }}
            </button>
          </div>
        </div>

        <!-- Global leaderboard preview -->
        <div v-if="leaderboard.length" class="mt-6 bg-black/20 rounded-2xl border border-[#c89b3c]/15 overflow-hidden animate-fade">
          <div class="px-4 py-3 border-b border-white/10 text-center">
            <p class="text-[#c89b3c] text-[10px] font-mono tracking-widest font-bold">☢ HALL OF TUMORES · GLOBAL</p>
          </div>
          <div class="divide-y divide-white/5">
            <div v-for="entry in leaderboard.slice(0, 5)" :key="entry.nombre"
              class="flex items-center gap-3 px-4 py-2.5">
              <span class="font-mono font-bold text-sm w-5 shrink-0 text-center"
                :class="entry.position <= 3 ? 'text-[#c89b3c]' : 'text-white/20'">
                {{ entry.position <= 3 ? ['🥇','🥈','🥉'][entry.position - 1] : entry.position }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-white text-xs font-bold truncate">{{ entry.nombre }}</p>
                <p class="text-white/30 text-[10px] font-mono">{{ entry.apariciones }} apariciones</p>
              </div>
              <p :class="entry.avg_kda < 1 ? 'text-red-400' : entry.avg_kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                class="text-xs font-bold font-mono">{{ entry.avg_kda.toFixed(2) }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Results screen -->
    <div v-else class="p-6 max-w-7xl mx-auto w-full">

      <!-- Header -->
      <div class="flex items-center justify-between mb-8 animate-fade">
        <div>
          <h1 class="text-white font-mono text-3xl font-bold">Top Tumores</h1>
          <div class="flex items-center gap-2 mt-1">
            <p class="text-[#c89b3c] font-mono">{{ summoner }}</p>
            <span v-if="tier" :class="tierColor[tier] ?? 'text-white/40'" class="font-mono font-bold text-sm border border-current/30 px-2 py-0.5 rounded">
              {{ tier }}{{ division ? ' ' + division : '' }}
            </span>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="toggleSaveAccount"
            :class="isSaved ? 'bg-[#c89b3c]/20 border-[#c89b3c]/50 text-[#c89b3c] hover:bg-red-900/20 hover:border-red-500/30 hover:text-red-400' : 'border-white/20 text-white/60 hover:text-[#c89b3c] hover:border-[#c89b3c]/40'"
            class="px-3 py-2 text-sm border rounded-lg transition font-mono">
            {{ isSaved ? '⭐ Guardada' : '☆ Guardar' }}
          </button>
          <button @click="rollExcuse"
            class="px-3 py-2 text-sm text-yellow-200 hover:text-yellow-100 bg-yellow-900/20 border border-yellow-500/40 hover:border-yellow-500/70 rounded-lg transition font-mono">
            🎲 Excusa
          </button>
          <button @click="openAnalytics" :disabled="analyticsLoading"
            class="px-3 py-2 text-sm text-purple-300 hover:text-purple-200 bg-purple-950/30 border border-purple-500/40 hover:border-purple-500/70 rounded-lg transition font-mono disabled:opacity-30">
            📊 {{ analyticsLoading ? 'Analizando...' : 'Analíticas' }}
          </button>
          <button @click="() => searchLiveGame()" :disabled="liveLoading"
            class="px-3 py-2 text-sm text-red-300 hover:text-red-200 bg-red-950/30 border border-red-500/40 hover:border-red-500/70 rounded-lg transition font-mono disabled:opacity-30">
            <span class="inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse mr-1.5 align-middle"></span>{{ liveLoading ? 'Buscando...' : 'En directo' }}
          </button>
          <button @click="refresh" :disabled="loading"
            class="px-3 py-2 text-sm text-white/60 hover:text-[#c89b3c] border border-white/20 hover:border-[#c89b3c]/40 rounded-lg transition font-mono disabled:opacity-30">
            {{ loading ? '↻' : '↻' }} Refrescar
          </button>
          <button @click="shareProfile"
            class="px-3 py-2 text-sm text-white/60 hover:text-[#c89b3c] border border-white/20 hover:border-[#c89b3c]/40 rounded-lg transition font-mono"
            :title="'Copiar URL del perfil'">
            🔗 {{ shareCopied ? 'Copiado!' : 'Compartir' }}
          </button>
          <button @click="exportStatsImage" :disabled="exportingImage"
            class="px-3 py-2 text-sm text-white/60 hover:text-[#c89b3c] border border-white/20 hover:border-[#c89b3c]/40 rounded-lg transition font-mono disabled:opacity-30"
            title="Descarga una card PNG con tus stats">
            🖼 {{ exportingImage ? '...' : 'Card' }}
          </button>
          <button @click="showNotifications = !showNotifications"
            class="relative px-3 py-2 text-sm text-white/60 hover:text-[#c89b3c] border border-white/20 hover:border-[#c89b3c]/40 rounded-lg transition font-mono"
            title="Notificaciones">
            🔔
            <span v-if="unreadNotifCount > 0"
              class="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">{{ unreadNotifCount }}</span>
          </button>
          <button @click="logout"
            class="px-4 py-2 text-sm text-white/60 hover:text-white border border-white/20 hover:border-white/40 rounded-lg transition font-mono">
            Cerrar sesión
          </button>
        </div>
      </div>

      <!-- Tumor watch alerts -->
      <div v-if="alerts.length" class="mb-4 animate-fade">
        <div v-for="alert in alerts" :key="alert.nombre"
          class="flex items-center gap-3 bg-orange-950/40 border border-orange-500/40 rounded-xl px-4 py-3 mb-2">
          <span class="text-xl animate-spin-slow">☢️</span>
          <div class="flex-1">
            <p class="text-orange-300 font-mono font-bold text-sm">Tumor detectado en tus partidas</p>
            <p class="text-orange-400/70 text-xs font-mono">{{ alert.nombre }} ({{ alert.campeon }}) ha vuelto a jugar contigo</p>
          </div>
          <button @click="toggleWatch(alert.nombre)" class="text-orange-400/50 hover:text-orange-300 text-xs font-mono border border-orange-500/20 hover:border-orange-500/40 px-2 py-1 rounded transition">
            Dejar de vigilar
          </button>
        </div>
      </div>

      <!-- Personal stats panel -->
      <div v-if="personalStats" class="bg-black/30 rounded-xl border border-white/10 p-5 mb-6 animate-fade">
        <div class="flex items-center justify-between mb-4">
          <p class="text-white/30 text-[10px] font-mono tracking-widest">TUS ESTADÍSTICAS</p>
          <div v-if="losingStreak >= 3"
            class="flex items-center gap-1.5 bg-red-900/40 border border-red-500/50 px-3 py-1 rounded-full animate-pulse">
            <span class="text-sm">🔥</span>
            <span class="text-red-400 text-[11px] font-mono font-bold tracking-wider">RACHA NEGATIVA · {{ losingStreak }} DERROTAS</span>
          </div>
        </div>
        <div class="grid grid-cols-9 gap-3 text-center">
          <div>
            <p class="text-white text-xl font-bold">{{ personalStats.total_matches }}</p>
            <p class="text-white/40 text-[10px] font-mono">PARTIDAS</p>
          </div>
          <div>
            <p class="text-blue-400 text-xl font-bold">{{ personalStats.wins }}</p>
            <p class="text-white/40 text-[10px] font-mono">VICTORIAS</p>
          </div>
          <div>
            <p class="text-red-400 text-xl font-bold">{{ personalStats.losses }}</p>
            <p class="text-white/40 text-[10px] font-mono">DERROTAS</p>
          </div>
          <div>
            <p :class="personalStats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'" class="text-xl font-bold">{{ personalStats.win_rate }}%</p>
            <p class="text-white/40 text-[10px] font-mono">WIN RATE</p>
          </div>
          <div class="border-l border-white/10">
            <p :class="personalStats.avg_kda >= 3 ? 'text-green-400' : personalStats.avg_kda >= 2 ? 'text-yellow-400' : 'text-red-400'" class="text-xl font-bold">{{ personalStats.avg_kda }}</p>
            <p class="text-white/40 text-[10px] font-mono">KDA MEDIO</p>
          </div>
          <div>
            <p class="text-white/80 text-xl font-bold">{{ personalStats.avg_cs }}</p>
            <p class="text-white/40 text-[10px] font-mono">CS MEDIO</p>
          </div>
          <div>
            <p class="text-white/80 text-xl font-bold">{{ formatGold(personalStats.avg_damage) }}</p>
            <p class="text-white/40 text-[10px] font-mono">DMG MEDIO</p>
          </div>
          <div class="border-l border-white/10">
            <p class="text-red-400 text-xl font-bold">{{ personalStats.times_worst }}</p>
            <p class="text-white/40 text-[10px] font-mono">VECES TUMOR</p>
          </div>
          <div>
            <p class="text-orange-400 text-xl font-bold">{{ personalStats.times_best_and_lost }}</p>
            <p class="text-white/40 text-[10px] font-mono">MEJOR Y PERDIÓ</p>
          </div>
        </div>
      </div>

      <!-- Filter bar -->
      <div class="flex flex-wrap items-center gap-3 mb-4 animate-fade">
        <!-- Win/Loss -->
        <div class="flex rounded-lg overflow-hidden border border-white/10 bg-black/20">
          <button v-for="opt in [['all','Todos'],['win','Victoria'],['loss','Derrota']]" :key="opt[0]"
            @click="filterResult = opt[0] as any"
            :class="filterResult === opt[0] ? 'bg-white/20 text-white' : 'text-white/40 hover:text-white/70'"
            class="px-3 py-1.5 text-xs font-mono transition">
            {{ opt[1] }}
          </button>
        </div>

        <!-- Champion filter -->
        <select v-model="filterChampion"
          class="px-3 py-1.5 bg-black/30 border border-white/10 rounded-lg text-white/70 text-xs font-mono focus:outline-none focus:border-white/30 transition">
          <option value="">Todos los campeones</option>
          <option v-for="champ in availableChampions" :key="champ" :value="champ">{{ champ }}</option>
        </select>

        <!-- Days filter -->
        <div class="flex rounded-lg overflow-hidden border border-white/10 bg-black/20">
          <button v-for="[days, label] in [[0,'Todo'],[7,'7d'],[14,'14d'],[30,'30d']]" :key="days"
            @click="filterDays = days as number"
            :class="filterDays === days ? 'bg-white/20 text-white' : 'text-white/40 hover:text-white/70'"
            class="px-3 py-1.5 text-xs font-mono transition">
            {{ label }}
          </button>
        </div>

        <!-- Results count -->
        <span class="text-white/20 text-xs font-mono ml-auto">
          {{ filteredMatches.length }} / {{ matches.length }} partidas
        </span>

        <!-- Reset filters -->
        <button v-if="filterResult !== 'all' || filterChampion || filterDays !== 0"
          @click="filterResult = 'all'; filterChampion = ''; filterDays = 0"
          class="text-white/30 hover:text-white/60 text-xs font-mono transition">
          ✕ Limpiar
        </button>
      </div>

      <!-- Main content: match list + top tumor -->
      <div class="flex gap-6 items-start">

      <!-- Match list -->
      <div class="space-y-4 flex-1 min-w-0">
        <div v-for="(match, index) in filteredMatches" :key="match.match_id"
          class="relative bg-black/30 backdrop-blur-sm rounded-xl overflow-hidden border border-white/10 animate-fade hover:border-white/20 transition cursor-pointer"
          :style="{ animationDelay: `${Math.min(index * 55, 550)}ms` }"
          @click="openMatchDetail(match.match_id)">

          <!-- Remake overlay -->
          <div v-if="match.game_duration < 300"
            class="absolute inset-0 z-10 bg-black/60 backdrop-grayscale flex items-center justify-center rounded-xl">
            <p class="text-white/80 font-mono font-black text-4xl tracking-[0.3em] select-none">REMAKE</p>
          </div>

          <div class="flex items-stretch">

            <!-- Win/Loss bar -->
            <div :class="match.win ? 'bg-blue-500' : 'bg-red-500'" class="w-1.5 shrink-0"></div>

            <!-- My stats -->
            <div class="flex items-center gap-4 px-4 py-4 border-r border-white/10 min-w-[200px]">
              <div class="relative">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.my_champion}.png`"
                  class="w-12 h-12 rounded-lg" />
                <span :class="match.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="absolute -bottom-1 -right-1 text-white text-[9px] font-bold px-1 rounded font-mono">
                  {{ match.win ? 'W' : 'L' }}
                </span>
                <span v-if="match.best_and_lost"
                  class="absolute -top-2 -left-2 text-[11px]"
                  title="Mejor de tu equipo y aun así perdiste">
                  🫀
                </span>
                <span v-if="match.worst_is_me"
                  class="absolute -top-2 -right-2 text-[13px] animate-spin-slow"
                  title="Fuiste el peor de tu equipo">
                  ☢️
                </span>
              </div>
              <div>
                <p class="text-white/50 text-[10px] font-mono mb-0.5">TÚ · {{ match.my_champion }}</p>
                <p class="text-white text-sm font-bold">
                  {{ match.my_kills }}/{{ match.my_deaths }}/{{ match.my_assists }}
                </p>
                <p class="text-[#c89b3c] text-xs font-mono">{{ match.my_kda }} KDA</p>
                <p v-if="match.best_and_lost" class="text-orange-400 text-[10px] font-mono mt-0.5">mejor del equipo</p>
              </div>
            </div>

            <!-- Arrow -->
            <div class="flex items-center px-3 text-white/20 text-lg">→</div>

            <!-- Worst player -->
            <div class="flex items-center gap-3 px-4 py-3 flex-1 min-w-0">
              <div class="relative shrink-0">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.worst.campeon}.png`"
                  class="w-11 h-11 rounded-lg" />
                <span class="absolute -bottom-1 -right-1 bg-black/70 text-white text-[9px] font-bold px-1 rounded font-mono border border-white/20">
                  Lv{{ match.worst.champ_level }}
                </span>
              </div>

              <!-- Name + KDA -->
              <div class="min-w-0 w-28 shrink-0">
                <p class="text-white/50 text-[10px] font-mono truncate">{{ match.worst.campeon }}</p>
                <a :href="profileUrl(match.worst.nombre)" target="_blank" rel="noopener" @click.stop
                  class="text-white text-xs font-bold truncate block hover:text-[#c89b3c] hover:underline transition"
                  :title="`Abrir perfil de ${match.worst.nombre}`">{{ match.worst.nombre }}</a>
                <p class="text-xs mt-0.5">
                  <span class="text-green-400">{{ match.worst.kills }}</span>
                  <span class="text-white/30">/</span>
                  <span class="text-red-400">{{ match.worst.deaths }}</span>
                  <span class="text-white/30">/</span>
                  <span class="text-blue-400">{{ match.worst.assists }}</span>
                  <span :class="match.worst.kda < 1 ? 'text-red-400' : match.worst.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                    class="ml-1 font-mono font-bold">{{ match.worst.kda.toFixed(2) }}</span>
                </p>
              </div>

              <!-- Extra stats grid with team avg deltas -->
              <div class="grid grid-cols-4 gap-x-3 gap-y-1 flex-1 min-w-0">
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">CS</p>
                  <p :class="match.worst.cs < 80 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.cs }}</p>
                  <p :class="delta(match.worst.cs, match.worst.team_avg.cs).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.cs, match.worst.team_avg.cs).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">DMG</p>
                  <p :class="match.worst.damage < 5000 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ formatGold(match.worst.damage) }}</p>
                  <p :class="delta(match.worst.damage, match.worst.team_avg.damage).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.damage, match.worst.team_avg.damage).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">ORO</p>
                  <p class="text-yellow-400/80 text-xs font-bold">{{ formatGold(match.worst.gold) }}</p>
                  <p :class="delta(match.worst.gold, match.worst.team_avg.gold).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.gold, match.worst.team_avg.gold).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">MUERTO</p>
                  <p :class="match.worst.time_dead > 180 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ formatDuration(match.worst.time_dead) }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">VISIÓN</p>
                  <p :class="match.worst.vision_score < 10 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.vision_score }}</p>
                  <p :class="delta(match.worst.vision_score, match.worst.team_avg.vision).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.vision_score, match.worst.team_avg.vision).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">WARDS</p>
                  <p :class="match.worst.wards_placed < 3 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.wards_placed }}</p>
                </div>
                <div class="text-center col-span-2">
                  <p class="text-white/40 text-[9px] font-mono">DURACIÓN</p>
                  <p class="text-white/60 text-xs font-mono">{{ formatDuration(match.game_duration) }}</p>
                </div>
              </div>

              <!-- Tumor score + watch -->
              <div class="shrink-0 flex flex-col items-center justify-center gap-2 pl-3 border-l border-white/10 min-w-[64px]">
                <p :class="tumorColor(match.worst.tumor_score)" class="text-2xl font-black font-mono">{{ match.worst.tumor_score }}</p>
                <p :class="tumorColor(match.worst.tumor_score)" class="text-[9px] font-mono font-bold text-center leading-tight">{{ tumorLabel(match.worst.tumor_score) }}</p>
                <button v-if="!match.worst_is_me" @click.stop="toggleWatch(match.worst.nombre)"
                  :class="isWatched(match.worst.nombre) ? 'text-orange-400 border-orange-500/40' : 'text-white/20 border-white/10 hover:text-orange-300 hover:border-orange-500/30'"
                  :title="isWatched(match.worst.nombre) ? 'Dejar de vigilar' : 'Vigilar tumor'"
                  class="text-[10px] border rounded px-1.5 py-0.5 transition font-mono">
                  {{ isWatched(match.worst.nombre) ? '👁️' : '👁' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <p v-if="filteredMatches.length === 0" class="text-white/40 text-center py-12 font-mono">
          {{ matches.length === 0 ? 'No se encontraron partidas rankeds recientes.' : 'Ninguna partida coincide con los filtros.' }}
        </p>

        <!-- Load more -->
        <div class="pt-2 pb-4 text-center">
          <button v-if="hasMore" @click="loadMore" :disabled="loadingMore"
            class="px-6 py-2.5 bg-white/5 hover:bg-white/10 border border-white/15 hover:border-[#c89b3c]/40 text-white/60 hover:text-white font-mono text-sm rounded-lg transition disabled:opacity-40">
            {{ loadingMore ? 'Cargando...' : `Cargar más (${currentStart} cargadas)` }}
          </button>
          <p v-else-if="matches.length > 0" class="text-white/20 text-xs font-mono">
            No hay más partidas
          </p>
        </div>
      </div>

      <!-- Sidebar -->
      <div v-if="topTumores.length || leaderboard.length" class="w-72 shrink-0 sticky top-6 animate-fade space-y-3">

        <!-- Tab switcher -->
        <div class="flex rounded-xl overflow-hidden border border-white/10 bg-black/30">
          <button @click="sidebarTab = 'top5'" :class="sidebarTab === 'top5' ? 'bg-red-900/50 text-red-300 border-red-500/40' : 'text-white/40 hover:text-white/70'"
            class="flex-1 py-2 text-[11px] font-mono font-bold tracking-wider transition border-r border-white/10">
            ☢ TOP 5
          </button>
          <button @click="sidebarTab = 'global'" :class="sidebarTab === 'global' ? 'bg-[#c89b3c]/20 text-[#c89b3c] border-[#c89b3c]/30' : 'text-white/40 hover:text-white/70'"
            class="flex-1 py-2 text-[11px] font-mono font-bold tracking-wider transition">
            🌍 GLOBAL
          </button>
        </div>

        <!-- Top 5 tab -->
        <div v-if="sidebarTab === 'top5' && topTumores.length">

          <!-- #1 big portrait card -->
          <a :href="profileUrl(topTumores[0].nombre)" target="_blank" rel="noopener"
            :title="`Abrir perfil de ${topTumores[0].nombre}`"
            class="block rounded-2xl overflow-hidden border border-red-500/30 shadow-2xl shadow-red-900/30 mb-3 hover:border-red-400/60 hover:shadow-red-900/50 transition">
            <div class="relative">
              <img
                :src="`https://ddragon.leagueoflegends.com/cdn/img/champion/loading/${topTumores[0].campeon}_0.jpg`"
                class="w-full object-cover object-top"
                style="aspect-ratio: 308/340"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent"></div>
              <div class="absolute top-3 left-3 bg-red-600 text-white text-[10px] font-mono font-bold px-2 py-1 rounded tracking-widest">
                ☢ #1 TUMOR
              </div>
              <div class="absolute top-3 right-3 bg-black/60 text-red-400 text-xs font-mono font-bold px-2 py-1 rounded border border-red-500/40">
                x{{ topTumores[0].apariciones }}
              </div>
              <div class="absolute bottom-0 left-0 right-0 p-4">
                <p class="text-white font-bold text-base leading-tight truncate">{{ topTumores[0].nombre }}</p>
                <p class="text-white/50 text-xs font-mono">{{ topTumores[0].campeon }}</p>
              </div>
            </div>
            <div class="bg-[#0d1b2a] p-3">
              <div class="grid grid-cols-3 gap-2 text-center mb-2">
                <div>
                  <p class="text-green-400 text-base font-bold">{{ topTumores[0].total_kills }}</p>
                  <p class="text-white/40 text-[9px] font-mono">K</p>
                </div>
                <div>
                  <p class="text-red-400 text-base font-bold">{{ topTumores[0].total_deaths }}</p>
                  <p class="text-white/40 text-[9px] font-mono">D</p>
                </div>
                <div>
                  <p class="text-blue-400 text-base font-bold">{{ topTumores[0].total_assists }}</p>
                  <p class="text-white/40 text-[9px] font-mono">A</p>
                </div>
              </div>
              <div class="text-center border-t border-white/10 pt-2">
                <p :class="topTumores[0].avg_kda < 1 ? 'text-red-400' : topTumores[0].avg_kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-2xl font-bold font-mono">{{ topTumores[0].avg_kda.toFixed(2) }}</p>
                <p class="text-white/30 text-[9px] font-mono">KDA MEDIO</p>
              </div>
            </div>
          </a>

          <!-- #2-5 compact rows -->
          <div class="space-y-2">
            <a v-for="(tumor, i) in topTumores.slice(1)" :key="tumor.nombre"
              :href="profileUrl(tumor.nombre)" target="_blank" rel="noopener"
              :title="`Abrir perfil de ${tumor.nombre}`"
              class="flex items-center gap-3 bg-black/30 rounded-xl border border-white/10 px-3 py-2.5 hover:border-red-500/40 hover:bg-red-950/20 transition cursor-pointer">
              <span class="text-white/30 font-mono font-bold text-sm w-4 shrink-0">#{{ i + 2 }}</span>
              <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${tumor.campeon}.png`"
                class="w-8 h-8 rounded-lg shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-white text-xs font-bold truncate">{{ tumor.nombre }}</p>
                <p class="text-white/40 text-[10px] font-mono">{{ tumor.campeon }}</p>
              </div>
              <div class="text-right shrink-0">
                <p :class="tumor.avg_kda < 1 ? 'text-red-400' : tumor.avg_kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-xs font-bold font-mono">{{ tumor.avg_kda.toFixed(2) }}</p>
                <p class="text-white/30 text-[9px] font-mono">x{{ tumor.apariciones }}</p>
              </div>
            </a>
          </div>
        </div>

        <!-- Global leaderboard tab -->
        <div v-if="sidebarTab === 'global'" class="bg-black/30 rounded-2xl border border-[#c89b3c]/20 overflow-hidden">
          <div class="px-4 py-3 border-b border-white/10">
            <p class="text-[#c89b3c] text-[10px] font-mono tracking-widest font-bold">LEADERBOARD GLOBAL · PEORES JUGADORES</p>
          </div>
          <div v-if="leaderboard.length" class="divide-y divide-white/5">
            <a v-for="entry in leaderboard" :key="entry.nombre"
              :href="profileUrl(entry.nombre)" target="_blank" rel="noopener"
              :title="`Abrir perfil de ${entry.nombre}`"
              class="flex items-center gap-3 px-3 py-2.5 hover:bg-[#c89b3c]/10 transition cursor-pointer">
              <span :class="entry.position <= 3 ? 'text-[#c89b3c]' : 'text-white/20'"
                class="font-mono font-bold text-sm w-5 shrink-0 text-center">
                {{ entry.position <= 3 ? ['🥇','🥈','🥉'][entry.position - 1] : entry.position }}
              </span>
              <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${entry.campeon}.png`"
                class="w-7 h-7 rounded-md shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-white text-xs font-bold truncate">{{ entry.nombre }}</p>
                <p class="text-white/30 text-[10px] font-mono">{{ entry.apariciones }} apariciones</p>
              </div>
              <p :class="entry.avg_kda < 1 ? 'text-red-400' : entry.avg_kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                class="text-xs font-bold font-mono shrink-0">{{ entry.avg_kda.toFixed(2) }}</p>
            </a>
          </div>
          <div v-else class="px-4 py-8 text-center">
            <p class="text-white/30 text-xs font-mono">Aún no hay datos globales.<br>Busca más summoners.</p>
          </div>
        </div>
      </div>

      </div><!-- end flex -->
    </div>

    <!-- Match detail modal -->
    <Transition name="modal">
      <div v-if="selectedMatchId" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm overflow-y-auto"
        @click.self="closeMatchDetail">
        <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="closeMatchDetail">
        <div class="bg-[#0d1b2a] border border-white/15 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto my-auto">

          <!-- Modal header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-white/10">
            <div>
              <p class="text-white font-mono font-bold">Detalle de partida</p>
              <p v-if="matchDetail" class="text-white/30 text-xs font-mono">
                {{ formatDuration(matchDetail.game_duration) }} ·
                {{ new Date(matchDetail.game_date).toLocaleDateString('es-ES', { day:'numeric', month:'short', year:'numeric' }) }}
              </p>
            </div>
            <button @click="closeMatchDetail" class="text-white/40 hover:text-white text-xl transition">✕</button>
          </div>

          <!-- Loading -->
          <div v-if="loadingDetail" class="flex items-center justify-center py-16">
            <div class="w-full max-w-md px-6">
              <p class="text-white/50 font-mono text-xs text-center mb-5 animate-pulse" :key="loadingFlavor">{{ loadingFlavor }}</p>
              <div class="space-y-2">
                <div v-for="n in 5" :key="n" class="flex items-center gap-3 bg-white/5 rounded-lg p-3">
                  <div class="w-9 h-9 rounded-lg bg-white/10 shimmer"></div>
                  <div class="flex-1 space-y-1.5">
                    <div class="h-2.5 bg-white/10 rounded shimmer" :style="{ width: `${55 + (n*7)%35}%` }"></div>
                    <div class="h-2 bg-white/5 rounded shimmer" :style="{ width: `${30 + (n*11)%30}%` }"></div>
                  </div>
                  <div class="w-10 h-6 bg-white/10 rounded shimmer"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Scorecard -->
          <div v-else-if="matchDetail" class="p-4 space-y-3">
            <!-- Predicción retroactiva: tumor histórico de cada equipo antes de jugar -->
            <div class="bg-black/30 border border-white/10 rounded-xl p-3">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2 text-center">PREDICCIÓN PRE-PARTIDA · TUMOR HISTÓRICO DE EQUIPO</p>
              <div class="grid grid-cols-3 gap-3 items-center">
                <div class="text-center">
                  <p class="text-blue-400 text-[10px] font-mono tracking-widest">AZUL</p>
                  <p :class="tumorColor(matchPrediction.blueTumor)" class="text-2xl font-mono font-black">{{ matchPrediction.blueTumor }}</p>
                  <p class="text-white/30 text-[9px] font-mono">tumor equipo</p>
                </div>
                <div class="text-center">
                  <p class="text-[10px] font-mono text-white/40 mb-1">Predijo {{ matchPrediction.winner === 'blue' ? '🔵' : matchPrediction.winner === 'red' ? '🔴' : '⚖️' }}</p>
                  <p :class="matchPrediction.correct ? 'text-green-400' : matchPrediction.winner === 'tie' ? 'text-white/40' : 'text-red-400'"
                    class="text-sm font-mono font-bold">
                    {{ matchPrediction.winner === 'tie' ? 'IGUALADO' : matchPrediction.correct ? '✓ ACERTÓ' : '✗ FALLÓ' }}
                  </p>
                  <p class="text-white/50 text-[10px] font-mono mt-1">
                    Ganó {{ matchDetail.blue_win ? '🔵 Azul' : '🔴 Rojo' }}
                  </p>
                </div>
                <div class="text-center">
                  <p class="text-red-400 text-[10px] font-mono tracking-widest">ROJO</p>
                  <p :class="tumorColor(matchPrediction.redTumor)" class="text-2xl font-mono font-black">{{ matchPrediction.redTumor }}</p>
                  <p class="text-white/30 text-[9px] font-mono">tumor equipo</p>
                </div>
              </div>
            </div>
            <!-- Team label helper -->
            <template v-for="(team, ti) in [matchDetail.team_blue, matchDetail.team_red]" :key="ti">
              <div :class="(ti === 0 ? matchDetail.blue_win : !matchDetail.blue_win) ? 'border-blue-500/30' : 'border-red-500/30'"
                class="rounded-xl border overflow-hidden">
                <!-- Team header -->
                <div :class="(ti === 0 ? matchDetail.blue_win : !matchDetail.blue_win) ? 'bg-blue-900/30' : 'bg-red-900/20'"
                  class="px-4 py-2 flex items-center gap-3">
                  <span class="text-xs font-mono font-bold" :class="(ti === 0 ? matchDetail.blue_win : !matchDetail.blue_win) ? 'text-blue-400' : 'text-red-400'">
                    {{ ti === 0 ? '🔵 EQUIPO AZUL' : '🔴 EQUIPO ROJO' }}
                  </span>
                  <span class="text-[10px] font-mono px-2 py-0.5 rounded"
                    :class="(ti === 0 ? matchDetail.blue_win : !matchDetail.blue_win) ? 'bg-blue-500/20 text-blue-300' : 'bg-red-500/20 text-red-300'">
                    {{ (ti === 0 ? matchDetail.blue_win : !matchDetail.blue_win) ? 'VICTORIA' : 'DERROTA' }}
                  </span>
                </div>

                <!-- Players -->
                <div class="divide-y divide-white/5">
                  <div v-for="p in team" :key="p.puuid"
                    :class="p.nombre === summoner ? 'bg-yellow-900/10 border-l-2 border-yellow-500/50' : ''"
                    class="flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition">
                    <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${p.campeon}.png`"
                      class="w-9 h-9 rounded-lg shrink-0" />
                    <div class="w-36 min-w-0 shrink-0">
                      <a :href="profileUrl(p.nombre)" target="_blank" rel="noopener"
                        class="text-white text-xs font-bold truncate block hover:text-[#c89b3c] hover:underline transition"
                        :title="`Abrir perfil de ${p.nombre}`">
                        {{ p.nombre === summoner ? '⭐ ' + p.nombre : p.nombre }}
                      </a>
                      <p class="text-white/30 text-[10px] font-mono">{{ p.campeon }} · Lv{{ p.champ_level }}</p>
                    </div>
                    <div class="w-24 shrink-0 text-center">
                      <p class="text-white text-xs font-bold">{{ p.kills }}/{{ p.deaths }}/{{ p.assists }}</p>
                      <p :class="p.kda < 1 ? 'text-red-400' : p.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                        class="text-[10px] font-mono font-bold">{{ p.kda }} KDA</p>
                    </div>
                    <!-- Damage bar -->
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2">
                        <div class="flex-1 bg-white/10 rounded-full h-1.5 overflow-hidden">
                          <div :style="{ width: `${Math.round(p.damage / Math.max(...[...matchDetail.team_blue, ...matchDetail.team_red].map(x => x.damage)) * 100)}%` }"
                            :class="p.nombre === summoner ? 'bg-yellow-400' : 'bg-purple-400'"
                            class="h-full rounded-full transition-all"></div>
                        </div>
                        <span class="text-white/50 text-[10px] font-mono w-10 text-right shrink-0">{{ formatGold(p.damage) }}</span>
                      </div>
                    </div>
                    <div class="hidden sm:grid grid-cols-3 gap-3 shrink-0">
                      <div class="text-center w-10">
                        <p class="text-white/60 text-xs font-mono">{{ p.cs }}</p>
                        <p class="text-white/20 text-[9px] font-mono">CS</p>
                      </div>
                      <div class="text-center w-10">
                        <p class="text-yellow-400/70 text-xs font-mono">{{ formatGold(p.gold) }}</p>
                        <p class="text-white/20 text-[9px] font-mono">ORO</p>
                      </div>
                      <div class="text-center w-10">
                        <p class="text-white/60 text-xs font-mono">{{ p.vision_score }}</p>
                        <p class="text-white/20 text-[9px] font-mono">VIS</p>
                      </div>
                    </div>
                    <div class="text-center shrink-0 w-20 border-l border-white/10 pl-2 ml-1 grid grid-cols-2 gap-1">
                      <div :title="'Tumor de partida: cómo jugó hoy'">
                        <p :class="tumorColor(p.tumor_score ?? 0)" class="text-base font-mono font-black leading-none">{{ p.tumor_score ?? '·' }}</p>
                        <p class="text-white/30 text-[8px] font-mono mt-0.5">PART.</p>
                      </div>
                      <div :title="'Tumor histórico: media pre-partida'">
                        <p :class="tumorColor(p.prior_tumor_score ?? 0)" class="text-base font-mono font-black leading-none opacity-70">{{ p.prior_tumor_score ?? '·' }}</p>
                        <p class="text-white/30 text-[8px] font-mono mt-0.5">HIST.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
        </div>
      </div>
    </Transition>

    <!-- Live game modal -->
    <Transition name="modal">
      <div v-if="showLiveGame" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm overflow-y-auto"
        @click.self="closeLiveGame">
        <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="closeLiveGame">
        <div class="bg-[#0d1b2a] border border-red-500/30 rounded-2xl shadow-2xl shadow-red-900/30 w-full max-w-5xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto my-auto">
          <div class="flex items-center justify-between px-6 py-4 border-b border-white/10">
            <div class="flex items-center gap-3">
              <span class="inline-block w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse"></span>
              <p class="text-white font-mono font-bold">Partida en directo · Predicción de tumor</p>
              <div v-if="predictionStats && predictionStats.total > 0"
                class="flex items-center gap-1.5 bg-[#c89b3c]/10 border border-[#c89b3c]/30 px-2.5 py-1 rounded-lg">
                <span class="text-[9px] font-mono text-white/50 tracking-widest">ACIERTO GLOBAL</span>
                <span :class="predictionStats.accuracy >= 60 ? 'text-green-400' : predictionStats.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'"
                  class="text-xs font-mono font-bold">{{ predictionStats.accuracy }}%</span>
                <span class="text-white/30 text-[9px] font-mono">({{ predictionStats.correct }}/{{ predictionStats.total }})</span>
              </div>
            </div>
            <button @click="closeLiveGame" class="text-white/40 hover:text-white text-xl transition">✕</button>
          </div>

          <div v-if="liveLoading" class="flex flex-col items-center justify-center py-12 gap-4 px-8">
            <p class="text-white/70 font-mono text-sm">{{ liveProgress.step || 'Iniciando...' }}</p>
            <div class="w-full max-w-md bg-white/5 border border-white/10 rounded-full h-2 overflow-hidden">
              <div class="h-full bg-gradient-to-r from-red-500 to-orange-400 transition-all duration-500"
                :style="{ width: `${Math.min(100, (liveProgress.progress / Math.max(1, liveProgress.total)) * 100)}%` }"></div>
            </div>
            <p class="text-white/30 font-mono text-[10px]">{{ liveProgress.progress }}/{{ liveProgress.total }}</p>
          </div>

          <div v-else-if="liveError" class="py-16 text-center">
            <p class="text-red-400 font-mono text-sm">{{ liveError }}</p>
          </div>

          <div v-else-if="liveGame" class="p-4 sm:p-6">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">
              Tumor score promedio basado en últimas rankeds de cada jugador
            </p>

            <!-- Bans -->
            <div v-if="liveGame.bans && liveGame.bans.length" class="mb-3 flex items-center gap-3 bg-black/30 border border-white/10 rounded-xl px-3 py-2 flex-wrap">
              <span class="text-white/30 text-[10px] font-mono tracking-widest">BANS</span>
              <div class="flex gap-1.5 flex-wrap">
                <img v-for="b in liveGame.bans" :key="`${b.team_id}-${b.champion_id}`"
                  :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${b.champion_name}.png`"
                  :alt="b.champion_name"
                  :title="b.champion_name"
                  class="w-7 h-7 rounded border border-white/10 grayscale opacity-70" />
              </div>
            </div>

            <!-- Blacklist warning -->
            <div v-if="blacklistedInTeam.length"
              class="mb-3 flex items-center gap-3 bg-red-950/40 border border-red-500/40 rounded-xl px-4 py-2.5 animate-pulse">
              <span class="text-2xl">🚫</span>
              <div class="flex-1">
                <p class="text-red-300 font-mono text-sm font-bold">Champ en blacklist en tu equipo</p>
                <p class="text-red-400/70 text-[11px] font-mono">
                  {{ blacklistedInTeam.map(p => p.champion_name).join(', ') }} — históricamente pierdes con estos picks
                </p>
              </div>
            </div>

            <!-- Win prediction · tumor de equipo en escala 0-100 (menor = mejor) -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4 items-center">
              <div class="bg-blue-950/40 border rounded-xl px-4 py-3 text-center"
                :class="livePrediction.winner === 'blue' ? 'border-blue-400/70 shadow-lg shadow-blue-500/20' : 'border-blue-500/20'">
                <p class="text-blue-400 text-[10px] font-mono tracking-widest">EQUIPO AZUL</p>
                <p :class="tumorColor(livePrediction.blueTumor)" class="text-3xl font-mono font-black mt-1">{{ livePrediction.blueTumor }}</p>
                <p class="text-blue-300/60 text-[9px] font-mono">tumor de equipo</p>
              </div>
              <div class="text-center">
                <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">PREDICCIÓN</p>
                <p class="text-2xl">{{ livePrediction.winner === 'blue' ? '🔵' : livePrediction.winner === 'red' ? '🔴' : '⚖️' }}</p>
                <p :class="livePrediction.winner === 'blue' ? 'text-blue-300' : livePrediction.winner === 'red' ? 'text-red-300' : 'text-white/50'"
                  class="text-[10px] font-mono font-bold mt-1">
                  {{ livePrediction.winner === 'blue' ? 'GANA AZUL' : livePrediction.winner === 'red' ? 'GANA ROJO' : 'IGUALADO' }}
                </p>
                <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ livePrediction.confidence }}% conf.</p>
              </div>
              <div class="bg-red-950/40 border rounded-xl px-4 py-3 text-center"
                :class="livePrediction.winner === 'red' ? 'border-red-400/70 shadow-lg shadow-red-500/20' : 'border-red-500/20'">
                <p class="text-red-400 text-[10px] font-mono tracking-widest">EQUIPO ROJO</p>
                <p :class="tumorColor(livePrediction.redTumor)" class="text-3xl font-mono font-black mt-1">{{ livePrediction.redTumor }}</p>
                <p class="text-red-300/60 text-[9px] font-mono">tumor de equipo</p>
              </div>
            </div>

            <!-- Resolve prediction (comprobar resultado) -->
            <div class="flex items-center justify-center gap-3 mb-4">
              <button @click="resolveLivePrediction" :disabled="resolving"
                class="text-xs font-mono px-3 py-1.5 border border-white/15 text-white/60 hover:text-[#c89b3c] hover:border-[#c89b3c]/40 rounded transition disabled:opacity-30">
                {{ resolving ? 'Comprobando...' : '✅ Comprobar resultado' }}
              </button>
              <button @click="searchLiveGame(true)" :disabled="liveLoading"
                class="text-xs font-mono px-3 py-1.5 border border-white/15 text-white/60 hover:text-[#c89b3c] hover:border-[#c89b3c]/40 rounded transition disabled:opacity-30"
                title="Recalcula priors saltando la caché de 6h">
                ↻ Forzar refresh
              </button>
              <button v-if="liveGame && liveGame.match_id" @click="openCreateBet"
                class="text-xs font-mono px-3 py-1.5 border border-yellow-500/40 text-yellow-300 hover:bg-yellow-900/20 hover:border-yellow-400/70 rounded transition"
                title="Apuesta TC contra otro user sobre el resultado">
                ☢ Apostar
              </button>
              <div v-if="resolveResult" class="text-xs font-mono flex items-center gap-2">
                <template v-if="(resolveResult as any).pending">
                  <span class="text-yellow-400">⏳ {{ (resolveResult as any).pending }}</span>
                </template>
                <template v-else>
                  <span :class="resolveResult.correct ? 'text-green-400' : 'text-red-400'">{{ resolveResult.correct ? '✓ ACERTÓ' : '✗ FALLÓ' }}</span>
                  <span class="text-white/40">predijo {{ resolveResult.predicted === 'blue' ? '🔵' : resolveResult.predicted === 'red' ? '🔴' : '⚖️' }} · ganó {{ resolveResult.actual === 'blue' ? '🔵' : '🔴' }}</span>
                </template>
              </div>
            </div>

            <!-- Lane matchups -->
            <div v-if="laneMatchups.length" class="mb-4 bg-black/20 border border-white/10 rounded-xl p-3">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">⚔ MATCHUPS POR LÍNEA</p>
              <div class="space-y-1.5">
                <div v-for="m in laneMatchups" :key="m.role"
                  class="grid grid-cols-[44px_1fr_50px_1fr] gap-2 items-center text-[11px] font-mono">
                  <span class="text-white/50 text-[10px] font-bold text-center">{{ ROLE_LABEL[m.role] || m.role.slice(0,3) }}</span>
                  <div class="flex items-center gap-2 justify-end min-w-0"
                    :class="m.edge === 'blue' ? 'text-blue-300' : m.edge === 'red' ? 'text-white/40' : 'text-white/60'">
                    <span class="truncate text-[10px]">{{ m.blue.nombre.split('#')[0] }}</span>
                    <span :class="tumorColor(m.blue.avg_tumor_score ?? 0)" class="font-bold w-6 text-right">{{ m.blue.avg_tumor_score ?? '?' }}</span>
                  </div>
                  <div class="text-center">
                    <span v-if="m.edge === 'blue'" class="text-blue-400">◀</span>
                    <span v-else-if="m.edge === 'red'" class="text-red-400">▶</span>
                    <span v-else class="text-white/20">=</span>
                  </div>
                  <div class="flex items-center gap-2 min-w-0"
                    :class="m.edge === 'red' ? 'text-red-300' : m.edge === 'blue' ? 'text-white/40' : 'text-white/60'">
                    <span :class="tumorColor(m.red.avg_tumor_score ?? 0)" class="font-bold w-6">{{ m.red.avg_tumor_score ?? '?' }}</span>
                    <span class="truncate text-[10px]">{{ m.red.nombre.split('#')[0] }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <!-- Blue team -->
              <div>
                <p class="text-blue-400 text-[11px] font-mono font-bold mb-2 tracking-widest">EQUIPO AZUL</p>
                <div class="space-y-2">
                  <div v-for="p in liveGame.players.filter(x => x.team_id === 100)" :key="p.puuid"
                    :class="p.is_me ? 'border-[#c89b3c]/60 bg-[#c89b3c]/5' : 'border-white/10'"
                    class="flex items-center gap-3 bg-black/30 border rounded-xl p-3">
                    <div class="relative shrink-0">
                      <img v-if="champData[String(p.champion_id)]"
                        :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${champData[String(p.champion_id)]}.png`"
                        class="w-12 h-12 rounded-lg border border-white/20" />
                      <div class="absolute -right-1 top-0 flex flex-col gap-0.5">
                        <img v-if="p.spell1_id && spellIconUrl(p.spell1_id)" :src="spellIconUrl(p.spell1_id)" class="w-4 h-4 rounded-sm border border-black/60" />
                        <img v-if="p.spell2_id && spellIconUrl(p.spell2_id)" :src="spellIconUrl(p.spell2_id)" class="w-4 h-4 rounded-sm border border-black/60" />
                      </div>
                      <div v-if="p.perks && p.perks.primary" class="absolute -left-1 -bottom-1 flex gap-0.5">
                        <span class="w-3 h-3 rounded-full border border-black/60"
                          :style="{ background: (RUNE_STYLES[p.perks.primary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.primary || 0]?.name || ''"></span>
                        <span v-if="p.perks.secondary" class="w-2 h-2 rounded-full border border-black/60 self-end"
                          :style="{ background: (RUNE_STYLES[p.perks.secondary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.secondary || 0]?.name || ''"></span>
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <span v-if="p.is_watched" title="En tu watch list" class="text-base">💀</span>
                        <a v-if="!p.streamer_mode" :href="profileUrl(p.nombre)" target="_blank" rel="noopener"
                          class="text-white text-sm font-mono truncate hover:text-[#c89b3c] hover:underline transition"
                          :class="p.is_watched ? 'text-red-300' : ''"
                          :title="`Abrir perfil de ${p.nombre}`">{{ p.nombre }}{{ p.is_me ? ' (TÚ)' : '' }}</a>
                        <p v-else class="text-white/60 text-sm font-mono truncate italic">{{ p.nombre }}</p>
                        <span v-if="p.streamer_mode" title="Modo streamer activado — score estimado con la media del equipo"
                          class="text-[9px] font-mono font-bold bg-sky-500/20 border border-sky-400/40 text-sky-300 px-1.5 py-0.5 rounded">🥷 STREAMER</span>
                        <span v-if="p.is_main" class="text-[9px] font-mono font-bold bg-purple-500/20 border border-purple-400/40 text-purple-300 px-1.5 py-0.5 rounded">🎯 MAIN</span>
                        <span v-if="p.smurf_signals && p.smurf_signals.length"
                          :title="p.smurf_signals.join(' · ')"
                          class="text-[9px] font-mono font-bold bg-pink-500/20 border border-pink-400/40 text-pink-300 px-1.5 py-0.5 rounded animate-pulse">🥷 SUS</span>
                        <span v-if="p.is_tilted" title="Tilteado: últimas 3 partidas muy malas"
                          class="text-[9px] font-mono font-bold bg-orange-500/20 border border-orange-400/40 text-orange-300 px-1.5 py-0.5 rounded animate-pulse">🔥 TILT</span>
                        <span v-if="p.is_hotstreak" title="Hotstreak: últimas 3 partidas jugando muy bien"
                          class="text-[9px] font-mono font-bold bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 px-1.5 py-0.5 rounded">📈 HOT</span>
                        <span v-if="p.duo_group"
                          title="Posible duo detectado en partidas recientes"
                          class="text-[9px] font-mono font-bold bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 px-1.5 py-0.5 rounded">DUO {{ p.duo_group }}</span>
                        <button @click.stop="toggleBlacklist(p.champion_name)" :title="championBlacklist.includes(p.champion_name) ? 'Quitar de blacklist' : 'Añadir a blacklist'"
                          class="text-[9px] font-mono px-1 py-0.5 rounded border transition"
                          :class="championBlacklist.includes(p.champion_name) ? 'bg-red-500/20 border-red-400/40 text-red-300' : 'border-white/10 text-white/30 hover:text-red-300 hover:border-red-500/40'">
                          {{ championBlacklist.includes(p.champion_name) ? '🚫' : '+' }}
                        </button>
                      </div>
                      <div class="flex items-center gap-2 flex-wrap">
                        <p :class="tierColor[p.tier] ?? 'text-white/40'" class="text-[10px] font-mono">{{ p.tier }} {{ p.division }}</p>
                        <p v-if="p.estimated_games > 0" class="text-[10px] font-mono text-white/50">
                          · ~{{ p.estimated_games }} games
                          <span class="text-white/30">(M{{ p.mastery_level }})</span>
                        </p>
                        <p v-if="p.champion_winrate !== null" class="text-[10px] font-mono"
                          :class="p.champion_winrate >= 60 ? 'text-green-400' : p.champion_winrate >= 50 ? 'text-yellow-400' : 'text-red-400'">
                          · {{ p.champion_winrate }}% WR ({{ p.champion_games }}/{{ p.champion_total_sample }})
                        </p>
                      </div>
                    </div>
                    <div class="text-right">
                      <p :class="[tumorColor(p.avg_tumor_score ?? 0), p.score_is_team_avg ? 'opacity-60 italic' : '']" class="text-2xl font-mono font-bold leading-none">
                        {{ p.avg_tumor_score ?? '?' }}{{ p.score_is_team_avg ? '*' : '' }}
                      </p>
                      <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ p.score_is_team_avg ? 'media equipo' : tumorLabel(p.avg_tumor_score ?? 0) }}</p>
                    </div>
                  </div>
                </div>
              </div>
              <!-- Red team -->
              <div>
                <p class="text-red-400 text-[11px] font-mono font-bold mb-2 tracking-widest">EQUIPO ROJO</p>
                <div class="space-y-2">
                  <div v-for="p in liveGame.players.filter(x => x.team_id === 200)" :key="p.puuid"
                    :class="p.is_me ? 'border-[#c89b3c]/60 bg-[#c89b3c]/5' : 'border-white/10'"
                    class="flex items-center gap-3 bg-black/30 border rounded-xl p-3">
                    <div class="relative shrink-0">
                      <img v-if="champData[String(p.champion_id)]"
                        :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${champData[String(p.champion_id)]}.png`"
                        class="w-12 h-12 rounded-lg border border-white/20" />
                      <div class="absolute -right-1 top-0 flex flex-col gap-0.5">
                        <img v-if="p.spell1_id && spellIconUrl(p.spell1_id)" :src="spellIconUrl(p.spell1_id)" class="w-4 h-4 rounded-sm border border-black/60" />
                        <img v-if="p.spell2_id && spellIconUrl(p.spell2_id)" :src="spellIconUrl(p.spell2_id)" class="w-4 h-4 rounded-sm border border-black/60" />
                      </div>
                      <div v-if="p.perks && p.perks.primary" class="absolute -left-1 -bottom-1 flex gap-0.5">
                        <span class="w-3 h-3 rounded-full border border-black/60"
                          :style="{ background: (RUNE_STYLES[p.perks.primary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.primary || 0]?.name || ''"></span>
                        <span v-if="p.perks.secondary" class="w-2 h-2 rounded-full border border-black/60 self-end"
                          :style="{ background: (RUNE_STYLES[p.perks.secondary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.secondary || 0]?.name || ''"></span>
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <span v-if="p.is_watched" title="En tu watch list" class="text-base">💀</span>
                        <a v-if="!p.streamer_mode" :href="profileUrl(p.nombre)" target="_blank" rel="noopener"
                          class="text-white text-sm font-mono truncate hover:text-[#c89b3c] hover:underline transition"
                          :class="p.is_watched ? 'text-red-300' : ''"
                          :title="`Abrir perfil de ${p.nombre}`">{{ p.nombre }}{{ p.is_me ? ' (TÚ)' : '' }}</a>
                        <p v-else class="text-white/60 text-sm font-mono truncate italic">{{ p.nombre }}</p>
                        <span v-if="p.streamer_mode" title="Modo streamer activado — score estimado con la media del equipo"
                          class="text-[9px] font-mono font-bold bg-sky-500/20 border border-sky-400/40 text-sky-300 px-1.5 py-0.5 rounded">🥷 STREAMER</span>
                        <span v-if="p.is_main" class="text-[9px] font-mono font-bold bg-purple-500/20 border border-purple-400/40 text-purple-300 px-1.5 py-0.5 rounded">🎯 MAIN</span>
                        <span v-if="p.smurf_signals && p.smurf_signals.length"
                          :title="p.smurf_signals.join(' · ')"
                          class="text-[9px] font-mono font-bold bg-pink-500/20 border border-pink-400/40 text-pink-300 px-1.5 py-0.5 rounded animate-pulse">🥷 SUS</span>
                        <span v-if="p.is_tilted" title="Tilteado: últimas 3 partidas muy malas"
                          class="text-[9px] font-mono font-bold bg-orange-500/20 border border-orange-400/40 text-orange-300 px-1.5 py-0.5 rounded animate-pulse">🔥 TILT</span>
                        <span v-if="p.is_hotstreak" title="Hotstreak: últimas 3 partidas jugando muy bien"
                          class="text-[9px] font-mono font-bold bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 px-1.5 py-0.5 rounded">📈 HOT</span>
                        <span v-if="p.duo_group"
                          title="Posible duo detectado en partidas recientes"
                          class="text-[9px] font-mono font-bold bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 px-1.5 py-0.5 rounded">DUO {{ p.duo_group }}</span>
                        <button @click.stop="toggleBlacklist(p.champion_name)" :title="championBlacklist.includes(p.champion_name) ? 'Quitar de blacklist' : 'Añadir a blacklist'"
                          class="text-[9px] font-mono px-1 py-0.5 rounded border transition"
                          :class="championBlacklist.includes(p.champion_name) ? 'bg-red-500/20 border-red-400/40 text-red-300' : 'border-white/10 text-white/30 hover:text-red-300 hover:border-red-500/40'">
                          {{ championBlacklist.includes(p.champion_name) ? '🚫' : '+' }}
                        </button>
                      </div>
                      <div class="flex items-center gap-2 flex-wrap">
                        <p :class="tierColor[p.tier] ?? 'text-white/40'" class="text-[10px] font-mono">{{ p.tier }} {{ p.division }}</p>
                        <p v-if="p.estimated_games > 0" class="text-[10px] font-mono text-white/50">
                          · ~{{ p.estimated_games }} games
                          <span class="text-white/30">(M{{ p.mastery_level }})</span>
                        </p>
                        <p v-if="p.champion_winrate !== null" class="text-[10px] font-mono"
                          :class="p.champion_winrate >= 60 ? 'text-green-400' : p.champion_winrate >= 50 ? 'text-yellow-400' : 'text-red-400'">
                          · {{ p.champion_winrate }}% WR ({{ p.champion_games }}/{{ p.champion_total_sample }})
                        </p>
                      </div>
                    </div>
                    <div class="text-right">
                      <p :class="[tumorColor(p.avg_tumor_score ?? 0), p.score_is_team_avg ? 'opacity-60 italic' : '']" class="text-2xl font-mono font-bold leading-none">
                        {{ p.avg_tumor_score ?? '?' }}{{ p.score_is_team_avg ? '*' : '' }}
                      </p>
                      <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ p.score_is_team_avg ? 'media equipo' : tumorLabel(p.avg_tumor_score ?? 0) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
    </Transition>

    <!-- Notifications sidebar -->
    <Transition name="modal">
      <div v-if="showNotifications" class="fixed top-0 right-0 bottom-0 w-80 z-[55] bg-[#0d1b2a]/95 backdrop-blur-md border-l border-white/10 shadow-2xl flex flex-col">
        <div class="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <p class="text-white/80 font-mono text-sm font-bold">🔔 Notificaciones</p>
          <div class="flex items-center gap-2">
            <button v-if="notifications.length" @click="markAllRead" class="text-[10px] font-mono text-white/40 hover:text-white/70">Limpiar</button>
            <button @click="showNotifications = false" class="text-white/40 hover:text-white text-lg">✕</button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div v-if="!notifications.length" class="py-12 text-center px-6">
            <p class="text-white/30 text-sm font-mono">Sin notificaciones</p>
            <p class="text-white/20 text-[11px] font-mono mt-2">Te avisaremos cuando se resuelvan predicciones, detectemos tumores recurrentes o cambios en tu WR semanal.</p>
          </div>
          <div v-else class="divide-y divide-white/5">
            <div v-for="n in notifications" :key="n.id"
              class="px-4 py-3 flex items-start gap-3 hover:bg-white/5 cursor-pointer transition group"
              @click="openNotification(n)">
              <span class="text-xl shrink-0">{{ n.icon }}</span>
              <div class="flex-1 min-w-0">
                <p class="text-white text-sm font-mono">{{ n.title }}</p>
                <p class="text-white/60 text-[11px] font-mono leading-snug">{{ n.body }}</p>
                <p v-if="n.match_id" class="text-white/20 text-[9px] font-mono mt-1 group-hover:text-[#c89b3c]/70">Click para ver la partida →</p>
              </div>
              <button @click.stop="dismissNotification(n.id)"
                class="text-white/20 hover:text-white/60 text-xs shrink-0" title="Descartar">✕</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Excuse toast -->
    <Transition name="excuse">
      <div v-if="excuseText" class="fixed top-6 right-6 z-[60] max-w-sm"
        @mouseenter="pauseExcuseTimer" @mouseleave="resumeExcuseTimer">
        <div class="bg-gradient-to-br from-yellow-900/90 to-amber-950/90 border border-yellow-500/50 rounded-xl shadow-2xl backdrop-blur overflow-hidden">
          <div class="p-4">
            <div class="flex items-start gap-3">
              <span class="text-2xl" :class="excuseRolling ? 'animate-spin' : ''">🎲</span>
              <div class="flex-1">
                <p class="text-yellow-300 text-[10px] font-mono tracking-widest mb-1">EXCUSA OFICIAL</p>
                <p class="text-yellow-100 font-mono text-sm leading-snug" :class="excuseRolling ? 'opacity-60 italic' : ''">{{ excuseText }}</p>
                <div class="flex gap-2 mt-3">
                  <button @click="rollExcuse" :disabled="excuseRolling" class="text-[10px] font-mono px-2 py-1 border border-yellow-500/30 text-yellow-300 rounded hover:border-yellow-500/60 disabled:opacity-40">🎲 Otra</button>
                  <button @click="closeExcuse" class="text-[10px] font-mono px-2 py-1 border border-white/10 text-white/40 rounded hover:text-white/70">Cerrar</button>
                </div>
              </div>
            </div>
          </div>
          <div class="h-1 bg-black/30">
            <div class="h-full bg-gradient-to-r from-yellow-400 to-amber-500 transition-[width] duration-100 ease-linear"
              :style="{ width: `${excuseTimerPct}%` }"></div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Analytics modal -->
    <Transition name="modal">
      <div v-if="showAnalytics" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm overflow-y-auto"
        @click.self="closeAnalytics">
        <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="closeAnalytics">
        <div class="bg-[#0d1b2a] border border-purple-500/30 rounded-2xl shadow-2xl shadow-purple-900/30 w-full max-w-5xl max-h-[92vh] overflow-y-auto my-auto">
          <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 sticky top-0 bg-[#0d1b2a]/95 backdrop-blur z-10">
            <p class="text-white font-mono font-bold">📊 Analíticas · {{ summoner }}</p>
            <button @click="closeAnalytics" class="text-white/40 hover:text-white text-xl transition">✕</button>
          </div>

          <div v-if="analyticsLoading" class="flex items-center justify-center py-16">
            <div class="w-full max-w-2xl px-6 py-8">
              <p class="text-white/50 font-mono text-xs text-center mb-6 animate-pulse" :key="loadingFlavor">{{ loadingFlavor }}</p>
              <div class="space-y-5">
                <div class="bg-white/5 rounded-xl p-5 h-24 shimmer"></div>
                <div class="bg-white/5 rounded-xl p-5 h-40 shimmer"></div>
                <div class="grid grid-cols-3 gap-3">
                  <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
                  <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
                  <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="analyticsError" class="py-16 text-center">
            <p class="text-red-400 font-mono text-sm">{{ analyticsError }}</p>
          </div>
          <div v-else-if="analyticsData" class="p-4 sm:p-6 space-y-8">

            <!-- Filter bar -->
            <section>
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">🔎 FILTROS</p>
              <div class="flex flex-wrap gap-2 items-center bg-black/30 border border-white/10 rounded-xl p-3">
                <select v-model="analyticsFilters.role" @change="loadAnalytics"
                  class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                  <option value="">Cualquier rol</option>
                  <option value="TOP">Top</option>
                  <option value="JUNGLE">Jungle</option>
                  <option value="MIDDLE">Mid</option>
                  <option value="BOTTOM">ADC</option>
                  <option value="UTILITY">Support</option>
                </select>
                <select v-model="analyticsFilters.result" @change="loadAnalytics"
                  class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                  <option value="">Todas</option>
                  <option value="win">Solo wins</option>
                  <option value="loss">Solo losses</option>
                </select>
                <select v-model="analyticsFilters.champion" @change="loadAnalytics"
                  class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1 max-w-[160px]">
                  <option value="">Cualquier champ</option>
                  <option v-for="c in analyticsData.champion_pool" :key="c.champion" :value="c.champion">
                    {{ c.champion }} ({{ c.games }})
                  </option>
                </select>
                <select v-model.number="analyticsFilters.count" @change="loadAnalytics"
                  class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                  <option :value="20">Últimas 20</option>
                  <option :value="30">Últimas 30</option>
                  <option :value="50">Últimas 50</option>
                </select>
                <button @click="analyticsFilters = { champion: '', role: '', result: '', count: 30 }; loadAnalytics()"
                  class="text-[11px] font-mono text-white/40 hover:text-white/70 px-2 py-1 border border-white/10 rounded">Reset</button>
                <span class="text-white/30 text-[10px] font-mono ml-auto">{{ analyticsData.total_matches }} partidas</span>
              </div>
            </section>

            <!-- Backtest del modelo -->
            <section>
              <div class="flex items-center justify-between mb-3">
                <p class="text-white/30 text-[10px] font-mono tracking-widest">🧪 BACKTEST DEL PREDICTOR</p>
                <button @click="runBacktest" :disabled="backtestLoading"
                  class="text-[11px] font-mono px-2.5 py-1 border border-purple-500/40 text-purple-300 hover:border-purple-400/80 rounded disabled:opacity-40">
                  {{ backtestLoading ? 'Procesando...' : (backtestData ? 'Volver a ejecutar' : 'Ejecutar') }}
                </button>
              </div>

              <!-- Progress bar mientras corre -->
              <div v-if="backtestLoading" class="bg-black/30 border border-purple-500/20 rounded-xl p-4 space-y-3">
                <p class="text-purple-200 font-mono text-xs">{{ backtestProgress.step || 'Procesando...' }}</p>
                <div class="w-full bg-white/5 border border-white/10 rounded-full h-2 overflow-hidden">
                  <div class="h-full bg-gradient-to-r from-purple-500 to-fuchsia-400 transition-all duration-500"
                    :style="{ width: `${Math.min(100, (backtestProgress.progress / Math.max(1, backtestProgress.total)) * 100)}%` }"></div>
                </div>
                <p class="text-white/40 font-mono text-[10px]">{{ backtestProgress.progress }}/{{ backtestProgress.total }} partidas — sigue navegando, te avisamos al terminar 🔔</p>
              </div>

              <!-- Resultado -->
              <div v-else-if="backtestData" class="bg-black/30 border border-purple-500/20 rounded-xl p-4">
                <div class="flex items-baseline gap-6">
                  <div>
                    <p :class="backtestData.accuracy >= 60 ? 'text-green-400' : backtestData.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'"
                      class="text-4xl font-mono font-black">{{ backtestData.accuracy }}%</p>
                    <p class="text-white/40 text-[10px] font-mono">acierto real</p>
                  </div>
                  <div class="text-sm font-mono text-white/60">
                    <p>{{ backtestData.correct }} / {{ backtestData.total }} aciertos</p>
                    <p class="text-white/30 text-xs">{{ backtestData.ties }} partidas sin predicción clara</p>
                  </div>
                </div>
              </div>
              <p v-else class="text-white/30 font-mono text-xs">Ejecuta el modelo sobre tus últimas 20 partidas ya acabadas para ver su acierto real.</p>
            </section>

            <!-- Lane diff -->
            <section v-if="(analyticsData as any).lane_diff">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">⚔ DIFF VS TU LANER</p>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <div class="grid grid-cols-4 gap-4 text-center">
                  <div>
                    <p :class="(analyticsData as any).lane_diff.win_lane_rate >= 50 ? 'text-green-400' : 'text-red-400'"
                      class="text-3xl font-mono font-black">{{ (analyticsData as any).lane_diff.win_lane_rate }}%</p>
                    <p class="text-white/40 text-[10px] font-mono">ganaste lane</p>
                  </div>
                  <div>
                    <p :class="(analyticsData as any).lane_diff.avg_cs_diff > 0 ? 'text-green-400' : 'text-red-400'"
                      class="text-2xl font-mono font-black">{{ (analyticsData as any).lane_diff.avg_cs_diff > 0 ? '+' : '' }}{{ (analyticsData as any).lane_diff.avg_cs_diff }}</p>
                    <p class="text-white/40 text-[10px] font-mono">CS diff</p>
                  </div>
                  <div>
                    <p :class="(analyticsData as any).lane_diff.avg_dmg_diff > 0 ? 'text-green-400' : 'text-red-400'"
                      class="text-2xl font-mono font-black">{{ (analyticsData as any).lane_diff.avg_dmg_diff > 0 ? '+' : '' }}{{ Math.round((analyticsData as any).lane_diff.avg_dmg_diff / 1000) }}k</p>
                    <p class="text-white/40 text-[10px] font-mono">DMG diff</p>
                  </div>
                  <div>
                    <p :class="(analyticsData as any).lane_diff.avg_kda_diff > 0 ? 'text-green-400' : 'text-red-400'"
                      class="text-2xl font-mono font-black">{{ (analyticsData as any).lane_diff.avg_kda_diff > 0 ? '+' : '' }}{{ (analyticsData as any).lane_diff.avg_kda_diff }}</p>
                    <p class="text-white/40 text-[10px] font-mono">KDA diff</p>
                  </div>
                </div>
                <p class="text-white/30 text-[9px] font-mono mt-3 text-center">
                  Promedio sobre {{ (analyticsData as any).lane_diff.games }} partidas comparando contigo y tu rival directo en la misma posición.
                </p>
              </div>
            </section>

            <!-- Tilt forecast -->
            <section v-if="(analyticsData as any).tilt_forecast">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🌡 TILT FORECAST</p>
              <div class="bg-black/30 border rounded-xl p-4"
                :class="(analyticsData as any).tilt_forecast.score >= 60 ? 'border-red-500/40' : (analyticsData as any).tilt_forecast.score >= 30 ? 'border-yellow-500/40' : 'border-green-500/40'">
                <div class="flex items-baseline gap-4">
                  <p :class="(analyticsData as any).tilt_forecast.score >= 60 ? 'text-red-400' : (analyticsData as any).tilt_forecast.score >= 30 ? 'text-yellow-400' : 'text-green-400'"
                    class="text-4xl font-mono font-black">{{ (analyticsData as any).tilt_forecast.score }}</p>
                  <div>
                    <p class="text-white text-sm font-mono">Riesgo de tilt: <span class="font-bold uppercase">{{ (analyticsData as any).tilt_forecast.level }}</span></p>
                    <p class="text-white/60 text-xs font-mono italic">"{{ (analyticsData as any).tilt_forecast.advice }}"</p>
                  </div>
                </div>
                <ul v-if="(analyticsData as any).tilt_forecast.reasons.length" class="mt-3 space-y-1">
                  <li v-for="r in (analyticsData as any).tilt_forecast.reasons" :key="r"
                    class="text-white/50 text-[11px] font-mono flex items-center gap-2">
                    <span>·</span><span>{{ r }}</span>
                  </li>
                </ul>
              </div>
            </section>

            <!-- Weekly comparison -->
            <section v-if="analyticsData.week_stats.this || analyticsData.week_stats.last">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">📅 COMPARATIVA SEMANAL</p>
              <div class="grid grid-cols-2 gap-4">
                <div v-for="(w, label) in { 'Esta semana': analyticsData.week_stats.this, 'Semana pasada': analyticsData.week_stats.last }" :key="label"
                  class="bg-black/30 border border-white/10 rounded-xl p-4">
                  <p class="text-white/40 text-[10px] font-mono tracking-widest">{{ label }}</p>
                  <div v-if="w" class="flex items-end gap-4 mt-2">
                    <div>
                      <p class="text-white text-2xl font-mono font-black">{{ w.games }}</p>
                      <p class="text-white/30 text-[9px] font-mono">partidas</p>
                    </div>
                    <div>
                      <p :class="w.winrate >= 50 ? 'text-green-400' : 'text-red-400'" class="text-2xl font-mono font-black">{{ w.winrate }}%</p>
                      <p class="text-white/30 text-[9px] font-mono">WR ({{ w.wins }}W)</p>
                    </div>
                    <div>
                      <p :class="tumorColor(w.avg_tumor)" class="text-2xl font-mono font-black">{{ w.avg_tumor }}</p>
                      <p class="text-white/30 text-[9px] font-mono">tumor medio</p>
                    </div>
                  </div>
                  <p v-else class="text-white/30 text-xs font-mono mt-3">Sin partidas</p>
                </div>
              </div>
              <p v-if="weekDelta" class="text-white/40 text-xs font-mono mt-3">
                <span :class="weekDelta.better ? 'text-green-400' : 'text-red-400'">
                  {{ weekDelta.better ? '↓' : '↑' }} {{ Math.abs(weekDelta.pct) }}% de tumor vs semana pasada
                </span>
                — {{ weekDelta.better ? 'vas mejorando' : 'vas peor' }}
              </p>
            </section>

            <!-- Tumor evolution line chart (SVG) -->
            <section v-if="analyticsData.evolution.length > 1">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">📈 EVOLUCIÓN DEL TUMOR SCORE</p>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <svg :viewBox="`0 0 600 180`" class="w-full h-44">
                  <!-- gridlines -->
                  <line v-for="y in [0, 25, 50, 75, 100]" :key="y"
                    :x1="30" :x2="590" :y1="160 - y * 1.4" :y2="160 - y * 1.4"
                    stroke="rgba(255,255,255,0.07)" stroke-width="1" />
                  <text v-for="y in [0, 25, 50, 75, 100]" :key="`t${y}`"
                    :x="5" :y="164 - y * 1.4" fill="rgba(255,255,255,0.25)" font-size="9" font-family="monospace">{{ y }}</text>
                  <!-- area -->
                  <path :d="evolutionAreaPath" fill="url(#tumorGradient)" />
                  <defs>
                    <linearGradient id="tumorGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stop-color="rgba(239,68,68,0.4)" />
                      <stop offset="100%" stop-color="rgba(239,68,68,0)" />
                    </linearGradient>
                  </defs>
                  <!-- line -->
                  <polyline :points="evolutionLinePoints" fill="none" stroke="#f87171" stroke-width="1.8" />
                  <!-- dots -->
                  <circle v-for="(pt, i) in evolutionPoints" :key="i" :cx="pt.x" :cy="pt.y" r="3"
                    :fill="pt.win ? '#4ade80' : '#f87171'" stroke="#0d1b2a" stroke-width="1">
                    <title>{{ pt.champion }} · {{ pt.win ? 'WIN' : 'LOSS' }} · tumor {{ pt.tumor }}</title>
                  </circle>
                </svg>
                <p class="text-white/30 text-[9px] font-mono mt-1">Verde = win · Rojo = loss · Eje Y = tumor score</p>
              </div>
            </section>

            <!-- Horario tóxico -->
            <section v-if="analyticsData.hour_stats.length">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🕒 HORARIO TÓXICO</p>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <div class="flex items-end gap-[2px]" style="height: 140px;">
                  <div v-for="h in hourly24" :key="h.hour"
                    class="flex-1 h-full flex flex-col items-center justify-end gap-1 group relative">
                    <div class="w-full rounded-t transition-all relative"
                      :class="h.games === 0 ? 'bg-white/5' : h.winrate >= 60 ? 'bg-green-500/70' : h.winrate >= 50 ? 'bg-yellow-500/70' : 'bg-red-500/70'"
                      :style="{ height: h.games === 0 ? '4px' : `${Math.max(8, (h.avg_tumor / hourMaxTumor) * 100)}%` }"></div>
                    <span class="text-white/30 text-[8px] font-mono">{{ String(h.hour).padStart(2, '0') }}</span>
                    <div v-if="h.games > 0" class="hidden group-hover:block absolute -top-12 left-1/2 -translate-x-1/2 bg-black/95 border border-white/20 rounded px-2 py-1 text-[10px] font-mono text-white whitespace-nowrap z-10 shadow-xl">
                      {{ String(h.hour).padStart(2,'0') }}h · {{ h.games }}g · {{ h.winrate }}% WR · {{ h.avg_tumor }} tumor
                    </div>
                  </div>
                </div>
                <p class="text-white/30 text-[9px] font-mono mt-2">Altura = tumor medio · Color = winrate · Pasa el ratón por encima</p>
              </div>
            </section>

            <!-- Heatmap de roles -->
            <section v-if="analyticsData.role_combo_stats.length">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🎯 COMBOS DE ROLES (TÚ × COMPAÑERO)</p>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[9px] font-mono mb-2">Filas = tu rol · Columnas = rol del compañero</p>
                <table class="mx-auto text-[11px] font-mono border-separate border-spacing-1">
                  <thead>
                    <tr>
                      <th class="w-12"></th>
                      <th v-for="r in ['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY']" :key="r"
                        class="text-white/40 font-bold w-14 h-7 text-center">{{ r.slice(0,3) }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="my in ['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY']" :key="my">
                      <td class="text-white/40 font-bold w-12 text-right pr-2">{{ my.slice(0,3) }}</td>
                      <td v-for="other in ['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY']" :key="other"
                        class="w-14 h-10 text-center rounded font-bold" :style="heatmapCellStyle(my, other)">
                        {{ heatmapCellText(my, other) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <!-- Champion pool -->
            <section v-if="analyticsData.champion_pool && analyticsData.champion_pool.length">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🏆 CHAMPION POOL</p>
              <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
                <div v-for="c in analyticsData.champion_pool" :key="c.champion"
                  class="bg-black/30 border border-white/10 rounded-xl p-2 flex items-center gap-2">
                  <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${c.champion}.png`"
                    class="w-10 h-10 rounded-lg border border-white/20 shrink-0" />
                  <div class="min-w-0 flex-1">
                    <p class="text-white text-[11px] font-mono truncate">{{ c.champion }}</p>
                    <p class="text-[9px] font-mono">
                      <span :class="c.winrate >= 60 ? 'text-green-400' : c.winrate >= 50 ? 'text-yellow-400' : 'text-red-400'">{{ c.winrate }}%</span>
                      <span class="text-white/30"> · {{ c.games }}g</span>
                    </p>
                    <p :class="tumorColor(c.avg_tumor)" class="text-[9px] font-mono">{{ c.avg_tumor }} tumor</p>
                  </div>
                </div>
              </div>
            </section>

            <!-- Best teammates / Worst nemesis grid -->
            <section v-if="(analyticsData.best_teammates && analyticsData.best_teammates.length) || (analyticsData.worst_nemesis && analyticsData.worst_nemesis.length)">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-if="analyticsData.best_teammates && analyticsData.best_teammates.length">
                  <p class="text-green-400/70 text-[10px] font-mono tracking-widest mb-2">🌟 BEST TEAMMATES</p>
                  <div class="bg-black/30 border border-green-500/20 rounded-xl divide-y divide-white/5">
                    <div v-for="d in analyticsData.best_teammates" :key="d.puuid" class="flex items-center gap-3 px-3 py-2">
                      <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${d.top_champion}.png`"
                        class="w-8 h-8 rounded-lg border border-white/20" />
                      <div class="flex-1 min-w-0">
                        <p class="text-white text-[11px] font-mono truncate">{{ d.nombre }}</p>
                        <p class="text-white/30 text-[9px] font-mono">{{ d.games }} partidas</p>
                      </div>
                      <p class="text-green-400 text-sm font-mono font-black">{{ d.winrate }}%</p>
                    </div>
                  </div>
                </div>
                <div v-if="analyticsData.worst_nemesis && analyticsData.worst_nemesis.length">
                  <p class="text-red-400/70 text-[10px] font-mono tracking-widest mb-2">💢 WORST NEMESIS</p>
                  <div class="bg-black/30 border border-red-500/20 rounded-xl divide-y divide-white/5">
                    <div v-for="d in analyticsData.worst_nemesis" :key="d.puuid" class="flex items-center gap-3 px-3 py-2">
                      <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${d.top_champion}.png`"
                        class="w-8 h-8 rounded-lg border border-white/20" />
                      <div class="flex-1 min-w-0">
                        <p class="text-white text-[11px] font-mono truncate">{{ d.nombre }}</p>
                        <p class="text-white/30 text-[9px] font-mono">{{ d.games }} partidas</p>
                      </div>
                      <p class="text-red-400 text-sm font-mono font-black">{{ d.winrate }}%</p>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- Dúo ideal -->
            <section v-if="analyticsData.duo_stats.length">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🤝 ALIADOS RECURRENTES</p>
              <div class="bg-black/30 border border-white/10 rounded-xl divide-y divide-white/5">
                <div v-for="(d, i) in analyticsData.duo_stats" :key="d.puuid" class="flex items-center gap-3 px-4 py-3">
                  <span class="text-white/30 text-xs font-mono w-6">#{{ i + 1 }}</span>
                  <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${d.top_champion}.png`"
                    class="w-10 h-10 rounded-lg border border-white/20" />
                  <div class="flex-1 min-w-0">
                    <p class="text-white text-sm font-mono truncate">{{ d.nombre }}</p>
                    <p class="text-white/30 text-[10px] font-mono">{{ d.top_champion }} · {{ d.games }} partidas juntos</p>
                  </div>
                  <div class="text-right">
                    <p :class="d.winrate >= 60 ? 'text-green-400' : d.winrate >= 50 ? 'text-yellow-400' : 'text-red-400'"
                      class="text-lg font-mono font-black">{{ d.winrate }}%</p>
                    <p class="text-white/30 text-[9px] font-mono">{{ d.wins }}W/{{ d.games - d.wins }}L</p>
                  </div>
                </div>
              </div>
            </section>

          </div>
        </div>
        </div>
      </div>
    </Transition>

    <!-- Bet modal (crear / created / aceptar) -->
    <BetModal
      :show="betModalShow"
      :mode="betModalMode"
      :match-id="liveGame?.match_id"
      :game-id="liveGame?.game_id"
      :bet-to-accept="betToAccept"
      :participants="betParticipants"
      @close="betModalShow = false"
      @refresh="onBetRefresh"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, onMounted, onUnmounted } from 'vue'
import BetModal from './BetModal.vue'
import {
  SCAN_MESSAGES, LOADING_FLAVORS,
  EXCUSE_STARTERS, EXCUSE_REASONS, EXCUSE_ENDINGS,
  RUNE_STYLES, SUMMONER_SPELLS,
  ROLE_ORDER, ROLE_LABEL, TIER_COLORS,
  tumorColor, tumorLabel,
} from '../composables/overviewConstants'
import { API_BASE } from '../composables/useApi'

interface TeamAvg {
  kda: number
  cs: number
  damage: number
  vision: number
  gold: number
}

interface WorstPlayer {
  nombre: string
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  damage: number
  vision_score: number
  gold: number
  time_dead: number
  champ_level: number
  wards_placed: number
  tumor_score: number
  team_avg: TeamAvg
}

interface PersonalStats {
  total_matches: number
  wins: number
  losses: number
  win_rate: number
  times_worst: number
  times_best_and_lost: number
  avg_kda: number
  avg_cs: number
  avg_damage: number
}

interface TopTumor {
  nombre: string
  apariciones: number
  campeon: string
  total_kills: number
  total_deaths: number
  total_assists: number
  avg_kda: number
}

interface LeaderboardEntry {
  position: number
  nombre: string
  apariciones: number
  campeon: string
  total_kills: number
  total_deaths: number
  total_assists: number
  avg_kda: number
}

interface MatchOverview {
  match_id: string
  game_duration: number
  game_date: number
  win: boolean
  best_and_lost: boolean
  worst_is_me: boolean
  my_champion: string
  my_kills: number
  my_deaths: number
  my_assists: number
  my_kda: number
  my_cs: number
  my_damage: number
  worst: WorstPlayer
}

interface DetailPlayer {
  puuid: string
  nombre: string
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  damage: number
  gold: number
  vision_score: number
  wards_placed: number
  champ_level: number
  time_dead: number
  win: boolean
  tumor_score?: number
  prior_tumor_score?: number
}

interface MatchDetail {
  match_id: string
  game_duration: number
  game_date: number
  blue_win: boolean
  team_blue: DetailPlayer[]
  team_red: DetailPlayer[]
}

// Theme
const theme = inject('theme') as any

const ddragonVersion = ref('15.1.1') // fallback; overwritten on mount

const champData = ref<Record<string, string>>({})

// Cache de DDragon en localStorage con TTL de 24h.
// Versions.json + champion.json son ~250KB combinados; descargarlos cada
// page load es desperdicio. La data del parche cambia ~1 vez al mes.
const DDRAGON_CACHE_TTL_MS = 24 * 60 * 60 * 1000
const DDRAGON_CACHE_KEY = 'zuruweb-ddragon-cache'

const loadDDragonFromCache = (): { version: string, champMap: Record<string, string> } | null => {
  try {
    const raw = localStorage.getItem(DDRAGON_CACHE_KEY)
    if (!raw) return null
    const obj = JSON.parse(raw)
    if (!obj || typeof obj !== 'object') return null
    if (Date.now() - (obj.cached_at || 0) > DDRAGON_CACHE_TTL_MS) return null
    if (!obj.version || !obj.champMap) return null
    return { version: obj.version, champMap: obj.champMap }
  } catch {
    return null
  }
}

const saveDDragonToCache = (version: string, champMap: Record<string, string>) => {
  try {
    localStorage.setItem(DDRAGON_CACHE_KEY, JSON.stringify({
      version, champMap, cached_at: Date.now(),
    }))
  } catch {}
}

const cachedDDragon = loadDDragonFromCache()
if (cachedDDragon) {
  // Hit: usar datos cacheados sin llamar a DDragon
  ddragonVersion.value = cachedDDragon.version
  champData.value = cachedDDragon.champMap
} else {
  // Miss: descargar y guardar para los próximos 24h
  fetch('https://ddragon.leagueoflegends.com/api/versions.json')
    .then(r => r.json())
    .then(versions => {
      ddragonVersion.value = versions[0]
      return fetch(`https://ddragon.leagueoflegends.com/cdn/${versions[0]}/data/en_US/champion.json`)
    })
    .then(r => r ? r.json() : null)
    .then(data => {
      if (!data) return
      const map: Record<string, string> = {}
      for (const id in data.data) {
        map[data.data[id].key] = id
      }
      champData.value = map
      saveDDragonToCache(ddragonVersion.value, map)
    })
    .catch(() => {})
}

const formData = ref({ gameName: '', tagLine: '' })
const summoner = ref('')
const tier = ref('')
const division = ref('')
const matches = ref<MatchOverview[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const scanning = ref(false)

const loadingFlavor = ref(LOADING_FLAVORS[0])
const profileUrl = (nombre: string) => {
  const slug = nombre.replace('#', '-')
  return `${window.location.origin}${window.location.pathname}#/summoner/${encodeURIComponent(slug)}`
}

const shareCopied = ref(false)
const shareProfile = async () => {
  if (!summoner.value) return
  const slug = summoner.value.replace('#', '-')
  const url = `${window.location.origin}${window.location.pathname}#/summoner/${encodeURIComponent(slug)}`
  try {
    await navigator.clipboard.writeText(url)
    shareCopied.value = true
    setTimeout(() => { shareCopied.value = false }, 1500)
  } catch {}
}

const exportingImage = ref(false)
const exportStatsImage = async () => {
  if (!summoner.value || !personalStats.value) return
  exportingImage.value = true
  try {
    const canvas = document.createElement('canvas')
    canvas.width = 800
    canvas.height = 1000
    const ctx = canvas.getContext('2d')!

    // Fondo gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 1000)
    gradient.addColorStop(0, '#0d1b2a')
    gradient.addColorStop(1, '#1b2838')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, 800, 1000)

    // Header dorado
    ctx.fillStyle = '#c89b3c'
    ctx.fillRect(0, 0, 800, 80)
    ctx.fillStyle = '#000'
    ctx.font = 'bold 36px monospace'
    ctx.textAlign = 'center'
    ctx.fillText('☢ TUMOR TRACKER', 400, 52)

    // Summoner
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 32px monospace'
    ctx.fillText(summoner.value, 400, 140)
    ctx.fillStyle = (tier.value && tier.value !== 'UNRANKED') ? '#c89b3c' : '#888'
    ctx.font = '20px monospace'
    ctx.fillText(`${tier.value || 'UNRANKED'} ${division.value || ''}`, 400, 175)

    // Stats grid
    const ps = personalStats.value
    const stats = [
      { label: 'PARTIDAS', value: String(ps.total_matches) },
      { label: 'WIN RATE', value: `${ps.win_rate}%`, color: ps.win_rate >= 50 ? '#4ade80' : '#f87171' },
      { label: 'KDA MEDIO', value: ps.avg_kda.toFixed(2) },
      { label: 'TIMES WORST', value: String(ps.times_worst) },
    ]
    let y = 250
    for (let i = 0; i < stats.length; i++) {
      const row = Math.floor(i / 2)
      const col = i % 2
      const x = col === 0 ? 100 : 500
      const yy = y + row * 130
      // Card
      ctx.fillStyle = 'rgba(0,0,0,0.4)'
      ctx.fillRect(x, yy, 200, 100)
      ctx.strokeStyle = 'rgba(255,255,255,0.1)'
      ctx.strokeRect(x, yy, 200, 100)
      // Value
      ctx.fillStyle = stats[i].color || '#c89b3c'
      ctx.font = 'bold 36px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(stats[i].value, x + 100, yy + 50)
      // Label
      ctx.fillStyle = '#888'
      ctx.font = '12px monospace'
      ctx.fillText(stats[i].label, x + 100, yy + 80)
    }

    // Top 3 tumores (si hay)
    if (topTumores.value && topTumores.value.length) {
      ctx.fillStyle = '#dc2626'
      ctx.font = 'bold 16px monospace'
      ctx.textAlign = 'left'
      ctx.fillText('☢ TOP TUMORES', 80, 580)
      let ty = 615
      for (let i = 0; i < Math.min(3, topTumores.value.length); i++) {
        const t = topTumores.value[i]
        ctx.fillStyle = ['#c89b3c', '#a8a8a8', '#cd7f32'][i] || '#666'
        ctx.font = 'bold 18px monospace'
        ctx.fillText(`#${i + 1}`, 80, ty)
        ctx.fillStyle = '#fff'
        ctx.font = '16px monospace'
        ctx.fillText(t.nombre, 130, ty)
        ctx.fillStyle = '#888'
        ctx.font = '14px monospace'
        ctx.fillText(`${t.campeon} · ${t.apariciones}x · KDA ${t.avg_kda.toFixed(2)}`, 130, ty + 22)
        ty += 60
      }
    }

    // Footer
    ctx.fillStyle = '#888'
    ctx.font = '12px monospace'
    ctx.textAlign = 'center'
    ctx.fillText('tumor-tracker.vercel.app', 400, 970)

    const link = document.createElement('a')
    link.download = `tumor-tracker-${summoner.value.replace('#', '-')}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  } catch (e) {
    console.error(e)
  } finally {
    exportingImage.value = false
  }
}

const parseHashAndLoad = () => {
  const hash = window.location.hash || ''
  const m = hash.match(/^#\/summoner\/(.+)$/)
  if (!m) return
  const raw = decodeURIComponent(m[1])
  // Acepta "Name-TAG" o "Name#TAG"
  const sep = raw.includes('#') ? '#' : '-'
  const idx = raw.lastIndexOf(sep)
  if (idx < 0) return
  const name = raw.slice(0, idx)
  const tag = raw.slice(idx + 1)
  if (!name || !tag) return
  if (summoner.value === `${name}#${tag}`) return
  formData.value = { gameName: name, tagLine: tag }
  login()
}

onMounted(() => {
  parseHashAndLoad()
  window.addEventListener('hashchange', parseHashAndLoad)
})
onUnmounted(() => {
  window.removeEventListener('hashchange', parseHashAndLoad)
  if (loadingFlavorInterval) clearInterval(loadingFlavorInterval)
  if (scanInterval) clearInterval(scanInterval)
  stopGlobalPoller()
  stopBacktestPoller()
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})

const excuseText = ref('')
const excuseRolling = ref(false)
const EXCUSE_DURATION_MS = 8000
const excuseTimerPct = ref(100)
let excuseTimerId: ReturnType<typeof setInterval> | null = null
let excuseStartedAt = 0
let excuseRemaining = EXCUSE_DURATION_MS

const closeExcuse = () => {
  excuseText.value = ''
  if (excuseTimerId) {
    clearInterval(excuseTimerId)
    excuseTimerId = null
  }
}

const startExcuseTimer = () => {
  if (excuseTimerId) clearInterval(excuseTimerId)
  excuseRemaining = EXCUSE_DURATION_MS
  excuseStartedAt = Date.now()
  excuseTimerPct.value = 100
  excuseTimerId = setInterval(() => {
    if (excuseRolling.value) {
      // Mientras rueda el dado, la barra queda congelada.
      excuseStartedAt = Date.now()
      return
    }
    const elapsed = Date.now() - excuseStartedAt
    const pct = Math.max(0, (excuseRemaining - elapsed) / EXCUSE_DURATION_MS * 100)
    excuseTimerPct.value = pct
    if (pct <= 0) closeExcuse()
  }, 60)
}

const pauseExcuseTimer = () => {
  if (!excuseTimerId) return
  const elapsed = Date.now() - excuseStartedAt
  excuseRemaining = Math.max(0, excuseRemaining - elapsed)
  clearInterval(excuseTimerId)
  excuseTimerId = null
}

const resumeExcuseTimer = () => {
  if (excuseTimerId || !excuseText.value) return
  excuseStartedAt = Date.now()
  excuseTimerId = setInterval(() => {
    if (excuseRolling.value) {
      excuseStartedAt = Date.now()
      return
    }
    const elapsed = Date.now() - excuseStartedAt
    const pct = Math.max(0, (excuseRemaining - elapsed) / EXCUSE_DURATION_MS * 100)
    excuseTimerPct.value = pct
    if (pct <= 0) closeExcuse()
  }, 60)
}
const rollExcuse = () => {
  excuseRolling.value = true
  // Rueda un par de veces mostrando basura random y luego el resultado final.
  const frames = 8
  let i = 0
  const interval = setInterval(() => {
    i++
    const r1 = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
    excuseText.value = `🎲 ${r1}...`
    if (i >= frames) {
      clearInterval(interval)
      const s = EXCUSE_STARTERS[Math.floor(Math.random() * EXCUSE_STARTERS.length)]
      const a = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
      let b = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
      while (b === a) b = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
      const e = EXCUSE_ENDINGS[Math.floor(Math.random() * EXCUSE_ENDINGS.length)]
      excuseText.value = `${s} ${a}, también ${b}, ${e}`
      excuseRolling.value = false
      startExcuseTimer()
    }
  }, 70)
}


const scanMessage = ref(SCAN_MESSAGES[0])
let scanInterval: ReturnType<typeof setInterval> | null = null

watch(scanning, (v) => {
  // Lock scroll del body mientras corre el X-Ray para que no se pueda
  // scrollear el contenido detrás del overlay.
  if (typeof document !== 'undefined') {
    document.body.style.overflow = v ? 'hidden' : ''
  }
  if (v) {
    let i = 0
    scanMessage.value = SCAN_MESSAGES[Math.floor(Math.random() * SCAN_MESSAGES.length)]
    scanInterval = setInterval(() => {
      i = (i + 1) % SCAN_MESSAGES.length
      scanMessage.value = SCAN_MESSAGES[Math.floor(Math.random() * SCAN_MESSAGES.length)]
    }, 2200)
  } else if (scanInterval) {
    clearInterval(scanInterval)
    scanInterval = null
  }
})

const hasMore = ref(false)
const currentStart = ref(0)
const error = ref('')
const recentSummoners = ref<string[]>([])
const savedAccounts = ref<string[]>([])
const watchList = ref<string[]>([])
const alerts = ref<{ nombre: string; campeon: string }[]>([])
const leaderboard = ref<LeaderboardEntry[]>([])
const sidebarTab = ref<'top5' | 'global'>('top5')

// Filters
const filterResult = ref<'all' | 'win' | 'loss'>('all')
const filterChampion = ref('')
const filterDays = ref(0)

// Match detail modal
const selectedMatchId = ref<string | null>(null)
const matchDetail = ref<MatchDetail | null>(null)
const loadingDetail = ref(false)

const validMatches = computed(() => matches.value.filter(m => m.game_duration >= 300))

const availableChampions = computed(() => {
  const set = new Set(matches.value.map(m => m.my_champion))
  return [...set].sort()
})

const filteredMatches = computed(() => {
  let list = matches.value
  if (filterResult.value === 'win') list = list.filter(m => m.win)
  if (filterResult.value === 'loss') list = list.filter(m => !m.win)
  if (filterChampion.value) list = list.filter(m => m.my_champion === filterChampion.value)
  if (filterDays.value > 0) {
    const cutoff = Date.now() - filterDays.value * 24 * 3600 * 1000
    list = list.filter(m => m.game_date > cutoff)
  }
  return list
})

const openMatchDetail = async (matchId: string) => {
  selectedMatchId.value = matchId
  loadingDetail.value = true
  matchDetail.value = null
  try {
    const res = await fetch(`${API_BASE}/matchDetail/${matchId}?viewer_tier=${encodeURIComponent(tier.value || 'GOLD')}`)
    matchDetail.value = await res.json()
  } catch {}
  loadingDetail.value = false
}

const closeMatchDetail = () => {
  selectedMatchId.value = null
  matchDetail.value = null
}

const personalStats = computed<PersonalStats | null>(() => {
  const valid = validMatches.value
  const total = valid.length
  if (!total) return null
  const wins = valid.filter(m => m.win).length
  return {
    total_matches: total,
    wins,
    losses: total - wins,
    win_rate: Math.round(wins / total * 100),
    times_worst: valid.filter(m => m.worst_is_me).length,
    times_best_and_lost: valid.filter(m => m.best_and_lost).length,
    avg_kda: Math.round(valid.reduce((s, m) => s + m.my_kda, 0) / total * 100) / 100,
    avg_cs: Math.round(valid.reduce((s, m) => s + m.my_cs, 0) / total * 10) / 10,
    avg_damage: Math.round(valid.reduce((s, m) => s + m.my_damage, 0) / total),
  }
})

const topTumores = computed<TopTumor[]>(() => {
  const valid = validMatches.value.filter(m => !m.worst_is_me)
  if (!valid.length) return []

  const counts = new Map<string, WorstPlayer[]>()
  for (const m of valid) {
    const n = m.worst.nombre
    if (!counts.has(n)) counts.set(n, [])
    counts.get(n)!.push(m.worst)
  }

  return [...counts.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 5)
    .map(([nombre, players]) => {
      const tk = players.reduce((s, p) => s + p.kills, 0)
      const td = players.reduce((s, p) => s + p.deaths, 0)
      const ta = players.reduce((s, p) => s + p.assists, 0)
      const champMap = new Map<string, number>()
      for (const p of players) champMap.set(p.campeon, (champMap.get(p.campeon) ?? 0) + 1)
      const campeon = [...champMap.entries()].sort((a, b) => b[1] - a[1])[0][0]
      return {
        nombre,
        apariciones: players.length,
        campeon,
        total_kills: tk,
        total_deaths: td,
        total_assists: ta,
        avg_kda: Math.round((td === 0 ? tk + ta : (tk + ta) / td) * 100) / 100,
      }
    })
})

const losingStreak = computed(() => {
  let streak = 0
  for (const m of validMatches.value) {
    if (!m.win) streak++
    else break
  }
  return streak
})

const fetchRecent = async () => {
  try {
    const res = await fetch(`${API_BASE}/recentSummoners`)
    recentSummoners.value = await res.json()
  } catch {}
}

const fetchLeaderboard = async () => {
  try {
    const res = await fetch(`${API_BASE}/leaderboard`)
    leaderboard.value = await res.json()
  } catch {}
}

const fetchSavedAccounts = async () => {
  try {
    const res = await fetch(`${API_BASE}/savedAccounts`)
    savedAccounts.value = await res.json()
  } catch {}
}

const isSaved = computed(() => summoner.value && savedAccounts.value.includes(summoner.value))

const toggleSaveAccount = async () => {
  const method = isSaved.value ? 'DELETE' : 'POST'
  try {
    const res = await fetch(`${API_BASE}/savedAccounts`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: summoner.value })
    })
    savedAccounts.value = await res.json()
  } catch {}
}

const fetchWatchList = async () => {
  if (!summoner.value) return
  try {
    const res = await fetch(`${API_BASE}/watchList?summoner=${encodeURIComponent(summoner.value)}`)
    watchList.value = await res.json()
  } catch {}
}

const isWatched = (nombre: string) => watchList.value.includes(nombre)

const toggleWatch = async (nombre: string) => {
  const method = isWatched(nombre) ? 'DELETE' : 'POST'
  try {
    const res = await fetch(`${API_BASE}/watchList`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: summoner.value, tumor: nombre })
    })
    watchList.value = await res.json()
  } catch {}
}

const saveRecent = async (name: string) => {
  try {
    await fetch(`${API_BASE}/recentSummoners`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: name })
    })
    await fetchRecent()
  } catch {}
}

const loadRecent = (entry: string) => {
  const [gameName, tagLine] = entry.split('#')
  formData.value = { gameName, tagLine }
  login()
}

fetchRecent()
fetchLeaderboard()
fetchSavedAccounts()

const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

const formatGold = (g: number) => g >= 1000 ? `${(g / 1000).toFixed(1)}k` : String(g)

const login = async () => {
  loading.value = true
  scanning.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      game_name: formData.value.gameName,
      tag_line: formData.value.tagLine,
    })

    const res = await fetch(`${API_BASE}/getOverview?${params}`)
    const data = await res.json()

    if (!res.ok || data.error) throw new Error(data.error || 'Error al cargar el overview')

    await new Promise(r => setTimeout(r, 2500))

    summoner.value = data.summoner
    tier.value = data.tier ?? ''
    division.value = data.division ?? ''
    matches.value = data.matches
    hasMore.value = data.has_more ?? false
    currentStart.value = data.matches.length
    alerts.value = data.alerts ?? []
    saveRecent(data.summoner)
    fetchWatchList()
    fetchBlacklist()
    startGlobalPoller()
    const slug = data.summoner.replace('#', '-')
    if (!window.location.hash.includes(slug)) {
      history.replaceState(null, '', `#/summoner/${encodeURIComponent(slug)}`)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
    scanning.value = false
  }
}

const loadMore = async () => {
  loadingMore.value = true
  try {
    const params = new URLSearchParams({
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
      start: String(currentStart.value),
      tier: tier.value,
    })

    const res = await fetch(`${API_BASE}/getOverview?${params}`)
    const data = await res.json()

    if (!res.ok || data.error) throw new Error(data.error)

    matches.value = [...matches.value, ...data.matches]
    hasMore.value = data.has_more ?? false
    currentStart.value += data.matches.length
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loadingMore.value = false
  }
}

interface LivePlayer {
  puuid: string
  nombre: string
  champion_id: number
  team_id: number
  role: string
  tier: string
  division: string
  avg_tumor_score: number | null
  champion_games: number
  champion_total_sample: number
  champion_pct: number
  champion_winrate: number | null
  is_main: boolean
  is_tilted: boolean
  is_hotstreak?: boolean
  recent_losses: number
  recent_wins?: number
  recent_avg_tumor: number
  mastery_points: number
  mastery_level: number
  estimated_games: number
  is_me: boolean
  is_watched: boolean
  is_blacklisted: boolean
  champion_name: string
  streamer_mode?: boolean
  smurf_signals?: string[]
  score_is_team_avg?: boolean
  duo_group?: string
  duo_size?: number
  spell1_id?: number
  spell2_id?: number
  perks?: { keystone: number | null, primary: number | null, secondary: number | null } | null
}

interface BanInfo {
  team_id: number
  champion_id: number
  champion_name: string
  pick_turn: number
}

interface PlayerBreakdown {
  puuid: string
  score: number
  role: string
  role_weight: number
  sample_weight: number
  weight: number
  weighted_contribution: number
}
interface Prediction {
  blue_team_tumor: number
  red_team_tumor: number
  winner: 'blue' | 'red' | 'tie'
  confidence: number
  diff: number
  blue_breakdown: PlayerBreakdown[]
  red_breakdown: PlayerBreakdown[]
}
interface LiveGame {
  game_id: number
  match_id: string
  queue_id: number
  viewer_puuid?: string
  players: LivePlayer[]
  bans?: BanInfo[]
  prediction?: Prediction
}

interface EvolutionPoint { date: number; tumor: number; win: boolean; champion: string; kda: number }
interface HourStat { hour: number; games: number; winrate: number; avg_tumor: number }
interface WeekStat { games: number; wins: number; winrate: number; avg_tumor: number }
interface DuoStat { puuid: string; nombre: string; games: number; wins: number; winrate: number; top_champion: string }
interface RoleComboStat { my_role: string; other_role: string; games: number; wins: number; winrate: number }
interface ChampionPoolEntry { champion: string; games: number; wins: number; winrate: number; avg_tumor: number }
interface AnalyticsData {
  summoner: string
  tier: string
  total_matches: number
  evolution: EvolutionPoint[]
  hour_stats: HourStat[]
  week_stats: { this: WeekStat | null; last: WeekStat | null }
  duo_stats: DuoStat[]
  role_combo_stats: RoleComboStat[]
  champion_pool: ChampionPoolEntry[]
  best_teammates: DuoStat[]
  worst_nemesis: DuoStat[]
}

const analyticsData = ref<AnalyticsData | null>(null)
const analyticsLoading = ref(false)
const analyticsError = ref('')
const showAnalytics = ref(false)

const analyticsFilters = ref({
  champion: '',
  role: '',
  result: '',
  count: 30,
})
const backtestData = ref<any>(null)
const backtestLoading = ref(false)
const backtestProgress = ref({ step: '', progress: 0, total: 1 })
let backtestPollerId: ReturnType<typeof setInterval> | null = null

const loadAnalytics = async () => {
  analyticsLoading.value = true
  analyticsError.value = ''
  try {
    const params: Record<string, string> = {
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
      count: String(analyticsFilters.value.count || 30),
    }
    if (analyticsFilters.value.champion) params.champion = analyticsFilters.value.champion
    if (analyticsFilters.value.role) params.role = analyticsFilters.value.role
    if (analyticsFilters.value.result) params.result = analyticsFilters.value.result
    const qs = new URLSearchParams(params).toString()
    const res = await fetch(`${API_BASE}/playerAnalytics?${qs}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error')
    analyticsData.value = data
  } catch (err) {
    analyticsError.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    analyticsLoading.value = false
  }
}

const openAnalytics = async () => {
  showAnalytics.value = true
  analyticsData.value = null
  backtestData.value = null
  analyticsFilters.value = { champion: '', role: '', result: '', count: 30 }
  await loadAnalytics()
}

const stopBacktestPoller = () => {
  if (backtestPollerId) {
    clearInterval(backtestPollerId)
    backtestPollerId = null
  }
}

const runBacktest = async () => {
  if (backtestLoading.value) return
  backtestLoading.value = true
  backtestData.value = null
  backtestProgress.value = { step: 'Iniciando...', progress: 0, total: 20 }
  try {
    const startRes = await fetch(`${API_BASE}/backtest/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game_name: summoner.value.split('#')[0],
        tag_line: summoner.value.split('#')[1],
        count: 20,
      }),
    })
    const start = await startRes.json()
    if (!startRes.ok || start.error) throw new Error(start.error || 'Error')
    const jobId = start.job_id
    backtestProgress.value = { step: 'Procesando partidas...', progress: 0, total: start.total || 20 }

    // Polling cada 500ms para que el frontend siga vivo aunque el backtest tarde mucho.
    stopBacktestPoller()
    backtestPollerId = setInterval(async () => {
      try {
        const pRes = await fetch(`${API_BASE}/backtest/progress/${jobId}`)
        if (!pRes.ok) return
        const p = await pRes.json()
        backtestProgress.value = {
          step: p.step || '',
          progress: p.progress || 0,
          total: p.total || 1,
        }
        if (p.status === 'done') {
          stopBacktestPoller()
          backtestData.value = p.result
          backtestLoading.value = false
          // Notificación al terminar
          const acc = p.result?.accuracy ?? 0
          pushNotification({
            id: `backtest-${Date.now()}`,
            icon: '🧪',
            title: 'Backtest completado',
            body: `${acc}% de acierto sobre ${p.result?.total ?? 0} partidas decididas.`,
          })
        } else if (p.status === 'error') {
          stopBacktestPoller()
          backtestLoading.value = false
          pushNotification({
            id: `backtest-error-${Date.now()}`,
            icon: '⚠️',
            title: 'Backtest fallido',
            body: p.error || 'Error desconocido',
          })
        }
      } catch {}
    }, 500)
  } catch (e) {
    backtestLoading.value = false
    stopBacktestPoller()
  }
}

const closeAnalytics = () => {
  showAnalytics.value = false
  analyticsData.value = null
  analyticsError.value = ''
}

// Rellena las 24 horas con ceros para que el chart sea continuo.
const hourly24 = computed(() => {
  const map = new Map<number, any>()
  for (const h of analyticsData.value?.hour_stats ?? []) map.set(h.hour, h)
  const out = []
  for (let i = 0; i < 24; i++) {
    out.push(map.get(i) ?? { hour: i, games: 0, winrate: 0, avg_tumor: 0 })
  }
  return out
})

// Tope para normalizar las alturas: el tumor máximo de la muestra (mín 30
// para que no exploten valores muy bajos).
const hourMaxTumor = computed(() => {
  const max = Math.max(0, ...(analyticsData.value?.hour_stats ?? []).map(h => h.avg_tumor))
  return Math.max(30, max)
})

const weekDelta = computed(() => {
  const t = analyticsData.value?.week_stats.this
  const l = analyticsData.value?.week_stats.last
  if (!t || !l || !l.avg_tumor) return null
  const pct = Math.round(((t.avg_tumor - l.avg_tumor) / l.avg_tumor) * 100)
  return { pct, better: pct < 0 }
})

const evolutionPoints = computed(() => {
  const ev = analyticsData.value?.evolution ?? []
  if (!ev.length) return []
  const n = ev.length
  return ev.map((e, i) => ({
    x: 30 + (i / Math.max(1, n - 1)) * 560,
    y: 160 - e.tumor * 1.4,
    tumor: e.tumor,
    win: e.win,
    champion: e.champion,
  }))
})

const evolutionLinePoints = computed(() =>
  evolutionPoints.value.map(p => `${p.x},${p.y}`).join(' ')
)

const evolutionAreaPath = computed(() => {
  const pts = evolutionPoints.value
  if (pts.length < 2) return ''
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')
  return `${line} L${pts[pts.length - 1].x},160 L${pts[0].x},160 Z`
})

const heatmapCellStyle = (myRole: string, otherRole: string) => {
  const entry = analyticsData.value?.role_combo_stats.find(
    r => r.my_role === myRole && r.other_role === otherRole
  )
  if (!entry) {
    return {
      background: 'rgba(255,255,255,0.015)',
      color: 'rgba(255,255,255,0.12)',
      border: '1px dashed rgba(255,255,255,0.06)',
    }
  }
  const hue = entry.winrate >= 50 ? 120 : 0
  const alpha = Math.min(0.6, 0.15 + (Math.abs(entry.winrate - 50) / 50) * 0.5)
  return { background: `hsla(${hue}, 70%, 40%, ${alpha})`, color: 'white' }
}

const heatmapCellText = (myRole: string, otherRole: string) => {
  const entry = analyticsData.value?.role_combo_stats.find(
    r => r.my_role === myRole && r.other_role === otherRole
  )
  if (!entry) return '·'
  return `${entry.winrate}%`
}

const championBlacklist = ref<string[]>([])

const fetchBlacklist = async () => {
  if (!summoner.value) return
  try {
    const res = await fetch(`${API_BASE}/championBlacklist?summoner=${encodeURIComponent(summoner.value)}`)
    if (res.ok) championBlacklist.value = await res.json()
  } catch {}
}

const toggleBlacklist = async (champion: string) => {
  const method = championBlacklist.value.includes(champion) ? 'DELETE' : 'POST'
  try {
    const res = await fetch(`${API_BASE}/championBlacklist`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: summoner.value, champion }),
    })
    if (res.ok) championBlacklist.value = await res.json()
  } catch {}
}

const liveGame = ref<LiveGame | null>(null)
const predictionStats = ref<{ total: number, correct: number, accuracy: number, pending: number } | null>(null)

const fetchPredictionStats = async () => {
  try {
    const res = await fetch(`${API_BASE}/predictionStats`)
    if (res.ok) predictionStats.value = await res.json()
  } catch {}
}

const spellIconUrl = (id?: number) => {
  if (!id || !SUMMONER_SPELLS[id]) return ''
  return `https://ddragon.leagueoflegends.com/cdn/${ddragonVersion.value}/img/spell/${SUMMONER_SPELLS[id]}.png`
}

const blacklistedInTeam = computed(() => {
  if (!liveGame.value) return []
  const me = liveGame.value.players.find(p => p.is_me)
  if (!me) return []
  return liveGame.value.players.filter(
    p => p.team_id === me.team_id && !p.is_me && championBlacklist.value.includes(p.champion_name)
  )
})

const laneMatchups = computed(() => {
  if (!liveGame.value) return []
  const blue = liveGame.value.players.filter(p => p.team_id === 100)
  const red = liveGame.value.players.filter(p => p.team_id === 200)
  const byRoleBlue: Record<string, LivePlayer[]> = {}
  const byRoleRed: Record<string, LivePlayer[]> = {}
  for (const p of blue) (byRoleBlue[p.role] ||= []).push(p)
  for (const p of red) (byRoleRed[p.role] ||= []).push(p)
  return ROLE_ORDER.map(role => {
    const b = byRoleBlue[role]?.[0]
    const r = byRoleRed[role]?.[0]
    if (!b || !r) return null
    const bScore = b.avg_tumor_score ?? 50
    const rScore = r.avg_tumor_score ?? 50
    const diff = bScore - rScore
    let edge: 'blue' | 'red' | 'tie' = 'tie'
    if (Math.abs(diff) >= 5) edge = diff < 0 ? 'blue' : 'red'
    return { role, blue: b, red: r, edge }
  }).filter((x): x is NonNullable<typeof x> => !!x)
})


const matchPrediction = computed(() => {
  // Predicción retroactiva del partido (basada en histórico pre-partida).
  // Todos los números en escala 0-100. Sin negativos.
  if (!matchDetail.value) return { blueTumor: 0, redTumor: 0, winner: 'tie' as const, correct: false, confidence: 0 }
  const md: any = matchDetail.value
  const actualBlueWon = md.blue_win
  const p: Prediction | undefined = md.prediction
  if (!p) return { blueTumor: 0, redTumor: 0, winner: 'tie' as const, correct: false, confidence: 0 }
  const correct = (p.winner === 'blue' && actualBlueWon) || (p.winner === 'red' && !actualBlueWon)
  return {
    blueTumor: p.blue_team_tumor,
    redTumor: p.red_team_tumor,
    winner: p.winner,
    confidence: p.confidence,
    correct,
  }
})

const livePrediction = computed(() => {
  // Predicción del live. team_tumor en 0-100, gana el menor.
  if (!liveGame.value || !liveGame.value.prediction) {
    return { blueTumor: 0, redTumor: 0, winner: 'tie' as const, confidence: 0 }
  }
  const p = liveGame.value.prediction
  return {
    blueTumor: p.blue_team_tumor,
    redTumor: p.red_team_tumor,
    winner: p.winner,
    confidence: p.confidence,
  }
})

const liveLoading = ref(false)
const liveError = ref('')
const showLiveGame = ref(false)

// Notifications
interface Notification {
  id: string
  icon: string
  title: string
  body: string
  at: number
  match_id?: string
  correct?: boolean
}
const notifications = ref<Notification[]>([])
const showNotifications = ref(false)
const notifSeen = ref<Set<string>>(new Set(
  (localStorage.getItem('zuruweb-notif-seen') || '').split(',').filter(Boolean)
))

const pushNotification = (n: Omit<Notification, 'at'>) => {
  if (notifSeen.value.has(n.id)) return
  if (notifications.value.find(x => x.id === n.id)) return
  notifications.value = [{ ...n, at: Date.now() }, ...notifications.value].slice(0, 20)
}

const markAllRead = () => {
  const newSeen = new Set(notifSeen.value)
  for (const n of notifications.value) newSeen.add(n.id)
  notifSeen.value = newSeen
  localStorage.setItem('zuruweb-notif-seen', Array.from(newSeen).join(','))
  notifications.value = []
}

const dismissNotification = (id: string) => {
  notifSeen.value.add(id)
  localStorage.setItem('zuruweb-notif-seen', Array.from(notifSeen.value).join(','))
  notifications.value = notifications.value.filter(n => n.id !== id)
}

const openNotification = (n: Notification) => {
  if (n.match_id) {
    openMatchDetail(n.match_id)
  }
  dismissNotification(n.id)
}

const unreadNotifCount = computed(() => notifications.value.length)

// Bromas sobre campeones para las notificaciones
const CHAMPION_JOKES_HIT = [
  (c: string) => `Lo dije: ${c} iba a estar inting.`,
  (c: string) => `Ese ${c} llevaba el aura de tumor escrita en la frente.`,
  (c: string) => `Spoiler alert: ${c} no sabía ni los cooldowns.`,
  (c: string) => `${c} olvidó que tenía keyboard. El modelo no.`,
  (c: string) => `Confirmado, ${c} fue el paciente cero de la partida.`,
  (c: string) => `${c} jugando así debería pagar una cuota al seguro médico.`,
  (c: string) => `El modelo huele a ${c} a 10 partidas de distancia.`,
  (c: string) => `${c} convirtió su lane en un hospital. Sin anestesia.`,
  (c: string) => `Diagnóstico correcto: ${c} era el tumor primario.`,
  (c: string) => `Si ${c} fuera médico, ya le habrían quitado la licencia.`,
  (c: string) => `${c} era el culpable. Como siempre. Siguiente caso.`,
  (c: string) => `Te lo dije yo, te lo dice el modelo: ${c} es ratchet.`,
  (c: string) => `${c} se ha dejado el alma en la grieta. Por desgracia, la suya.`,
  (c: string) => `Detectar a ${c} era fácil: el KDA hablaba por sí solo.`,
  (c: string) => `Otra partida con ${c} de trending topic en el chat del equipo.`,
  (c: string) => `Tras el escáner: ${c} tenía metástasis en todos los mapas.`,
  (c: string) => `${c} y yo estamos de acuerdo: él es el problema.`,
  (c: string) => `Checkmate. ${c} fue justo el jugador que predije.`,
  (c: string) => `Si ${c} jugara peor habría que darle medalla.`,
  (c: string) => `El modelo le vio los últimos 3 games a ${c} y se frotó las manos.`,
  // Memes / referencias
  (c: string) => `${c} ha hecho lo que mejor sabe hacer: nada.`,
  (c: string) => `Bro, ${c} jugó como si tuviera 200 ping de WiFi de aeropuerto.`,
  (c: string) => `${c} when minute 5 hits: I sleep. Minute 25: real shit.`,
  (c: string) => `POV: eres ${c} y has elegido inting como personalidad.`,
  (c: string) => `${c} es la prueba viva de que en LoL no hay requisito mínimo de IQ.`,
  (c: string) => `${c} stop. Stop. Stop. Stop. Stop.`,
  (c: string) => `${c} jugando la partida que un domingo a las 3 AM, evidente.`,
  (c: string) => `Riot debería buscar a ${c} y agradecerle por inflar mi LP.`,
  (c: string) => `${c} pickea el champ, ${c} pickea el feed.`,
  (c: string) => `Ese ${c} salió del champ select directamente al 0/12.`,
  (c: string) => `${c} jugó sin ratón. Y aún así perdió contra una pared.`,
  (c: string) => `El historial de ${c} es un crime scene tape rodeando ARAM.`,
  (c: string) => `${c} en el late game: existe. Y poco más.`,
  (c: string) => `${c} se descargó LoL ayer y eligió ranked. Iconic.`,
  (c: string) => `Ese aura de "voy a perder por ${c}" la noté desde el loading screen.`,
  (c: string) => `${c} no sabe qué es un tower-dive y le dive cada partida.`,
  (c: string) => `${c} jugaba con la mano izquierda y tomando cerveza. Confirmed.`,
  (c: string) => `${c} se merece su propio capítulo en el DSM-5: "Mecánicas Negativas".`,
  (c: string) => `${c} streameaba para que mami lo viera. Mami se desconectó.`,
  (c: string) => `${c} promised a comeback. ${c} delivered a tutorial of how to lose.`,
  (c: string) => `${c} cuando ve un tumor: 👀 espejo.`,
  (c: string) => `Si Riot baneara por inting, ${c} ya sería un summoner free agent.`,
  (c: string) => `${c} jugó la partida con fe. Y solo eso.`,
  (c: string) => `${c}: el real "1v9" pero del lado equivocado.`,
  (c: string) => `Te juro que ${c} estaba leyendo TikToks entre cada teamfight.`,
  (c: string) => `${c} debe pensar que las wards son objetos decorativos.`,
  (c: string) => `${c} llegó al lane vacío y aún encontró forma de feedearse.`,
  (c: string) => `${c} se estaba defendiendo de fantasmas. Sus minions tampoco existían.`,
]
const CHAMPION_JOKES_MISS = [
  (c: string) => `Error de cálculo: ${c} tuvo un día lúcido.`,
  (c: string) => `Por una vez, ${c} no era el problema. Shock.`,
  (c: string) => `${c} se puso serio y el modelo se cayó del stack.`,
  (c: string) => `Felicitaciones a ${c} por trolear al predictor.`,
  (c: string) => `¿Quién iba a pensar que ${c} iba a funcionar? No yo.`,
  (c: string) => `${c} decidió hoy que no quería ser tumor. Raro.`,
  (c: string) => `El modelo pide disculpas a ${c}. Una vez. Solo hoy.`,
  (c: string) => `${c} te ha gaslighteado al predictor, enhorabuena.`,
  (c: string) => `Increíble: ${c} subió la nota desde el suspenso.`,
  (c: string) => `Error 404: tumor de ${c} not found. Esta vez.`,
  (c: string) => `${c} ha leído Sun Tzu entre partida y partida.`,
  (c: string) => `El modelo predijo feed, ${c} predijo MVP. Gana ${c}.`,
  (c: string) => `Hoy ${c} no tilteó. Mañana ya veremos.`,
  (c: string) => `${c} se saltó su promesa diaria de inting.`,
  (c: string) => `Hipótesis rechazada: ${c} no siempre es el peor.`,
  // Memes / referencias
  (c: string) => `${c} dijo "hold my beer" y carreó. Sad meta.`,
  (c: string) => `Plot twist: ${c} estaba alt-tabbed mirando guías esta vez.`,
  (c: string) => `${c} did the impossible: tener un día bueno. Calendario it.`,
  (c: string) => `${c}: "I am the storm that is approaching." El modelo: 😶`,
  (c: string) => `${c} ascended. Por una partida. Cobardes los que dudaron.`,
  (c: string) => `Bro, ${c} cooked. El predictor está reportado por fake news.`,
  (c: string) => `Una vez al año, ${c} es Faker. Hoy fue ese día.`,
  (c: string) => `${c} se medicó antes de la partida. Plot armor activado.`,
  (c: string) => `El modelo le debe un café (o un Panteón) a ${c}.`,
  (c: string) => `${c} just hit different today. Inexplicable.`,
  (c: string) => `Random ${c} buff: 100% winrate desde el cementerio del modelo.`,
  (c: string) => `${c} carried like un challenger borracho con suerte.`,
  (c: string) => `Confidential: ${c} ha estado practicando en mejores campos. Aquí.`,
  (c: string) => `${c} demostró que el modelo NO es Skynet. Aún.`,
  (c: string) => `Excusa del modelo: el clima, la luna, ${c} mejorando.`,
  (c: string) => `${c} se ha leído un libro y ahora es coach de Riot.`,
  (c: string) => `Trust the process. Hoy el process tenía nombre: ${c}.`,
  (c: string) => `${c} mid: "shut up and dance". Y bailó la partida.`,
  (c: string) => `${c} jugó como un challenger. Mañana volverá a ser ${c}.`,
  (c: string) => `Por primera vez, alguien le dio importancia al elo y se llamaba ${c}.`,
  (c: string) => `${c} sacó de su mochila un manual y se acordó de jugar.`,
]

const pickJoke = (champion: string, correct: boolean): string => {
  const arr = correct ? CHAMPION_JOKES_HIT : CHAMPION_JOKES_MISS
  const fn = arr[Math.floor(Math.random() * arr.length)]
  return fn(champion || 'ese tío')
}

// Dado un match_id busca el peor champion (mayor tumor) del equipo perdedor
const fetchWorstChampion = async (matchId: string): Promise<string> => {
  try {
    const res = await fetch(`${API_BASE}/matchDetail/${matchId}?viewer_tier=${encodeURIComponent(tier.value || 'GOLD')}`)
    if (!res.ok) return ''
    const data = await res.json()
    const losingBlue = !data.blue_win
    const losers = losingBlue ? data.team_blue : data.team_red
    if (!Array.isArray(losers) || !losers.length) return ''
    const worst = losers.reduce((a: any, b: any) =>
      ((b.tumor_score ?? 0) > (a.tumor_score ?? 0) ? b : a), losers[0])
    return worst?.campeon || ''
  } catch {
    return ''
  }
}

// Global poller: cada 60s revalida predicciones pendientes y lanza notificaciones.
let globalPollerId: ReturnType<typeof setInterval> | null = null
const startGlobalPoller = () => {
  if (globalPollerId) return
  const tick = async () => {
    try {
      const res = await fetch(`${API_BASE}/predictionStats`)
      if (!res.ok) return
      const data = await res.json()
      predictionStats.value = data
      if (!Array.isArray(data.recent)) return
      // Procesa cada predicción resuelta recientemente. El id es el match_id,
      // así que notifSeen deduplica por partida — aunque el poller vuelva a
      // encontrar la misma, no se vuelve a añadir.
      for (const entry of data.recent) {
        if (entry?.correct === undefined || !entry?.match_id) continue
        const id = `pred-${entry.match_id}`
        if (notifSeen.value.has(id)) continue
        if (notifications.value.find(x => x.id === id)) continue
        const correct = !!entry.correct
        // Fetch worst champion async y luego empuja la notificación con el chiste.
        fetchWorstChampion(entry.match_id).then(champ => {
          pushNotification({
            id,
            icon: correct ? '✅' : '❌',
            title: correct ? 'Predicción acertada' : 'Predicción fallada',
            body: pickJoke(champ, correct),
            match_id: entry.match_id,
            correct,
          })
        })
      }
    } catch {}
  }
  tick()
  globalPollerId = setInterval(tick, 60000)
}
const stopGlobalPoller = () => {
  if (globalPollerId) {
    clearInterval(globalPollerId)
    globalPollerId = null
  }
}

const liveProgress = ref({ step: '', progress: 0, total: 1 })
let liveAbort = false

const auth = inject<any>('auth')

const resolveResult = ref<{ predicted: string, actual: string, correct: boolean } | null>(null)

// Bet modal state
const betModalShow = ref(false)
const betModalMode = ref<'create' | 'created' | 'accept'>('create')
const betToAccept = ref<any>(null)

const openCreateBet = () => {
  if (!auth?.isLoggedIn.value) {
    alert('Necesitas hacer login con Discord para apostar')
    return
  }
  betModalMode.value = 'create'
  betModalShow.value = true
}

const onBetRefresh = () => {
  if (betModalMode.value === 'create') betModalMode.value = 'created'
}

const betParticipants = computed(() => {
  if (!liveGame.value?.players) return []
  return liveGame.value.players.map(p => ({
    puuid: p.puuid,
    name: p.nombre,
    championName: p.champion_name,
    teamId: p.team_id,
  }))
})

// Listen for bet links in URL hash
const checkBetHash = async () => {
  const m = window.location.hash.match(/^#\/bet\/([A-Z0-9]+)$/)
  if (!m) return
  const code = m[1]
  if (!auth?.isLoggedIn.value) {
    // Will retry after login; just store the intent
    return
  }
  const bet = await auth.fetchBet(code)
  if (!bet) {
    alert(`Apuesta ${code} no encontrada`)
    history.replaceState(null, '', window.location.pathname)
    return
  }
  if (bet.status !== 'open') {
    alert(`Esta apuesta ya está ${bet.status}`)
    history.replaceState(null, '', window.location.pathname)
    return
  }
  betToAccept.value = bet
  betModalMode.value = 'accept'
  betModalShow.value = true
  // Clear hash so refresh doesn't reopen
  history.replaceState(null, '', window.location.pathname)
}

onMounted(() => { checkBetHash() })
window.addEventListener('hashchange', checkBetHash)
const resolving = ref(false)

const resolveLivePrediction = async () => {
  if (!liveGame.value?.match_id || !liveGame.value?.viewer_puuid) return
  resolving.value = true
  resolveResult.value = null
  try {
    const res = await fetch(`${API_BASE}/resolvePrediction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        match_id: liveGame.value.match_id,
        viewer_puuid: liveGame.value.viewer_puuid,
      }),
    })
    const data = await res.json()
    if (data.resolved) {
      resolveResult.value = {
        predicted: data.predicted_winner,
        actual: data.actual_winner,
        correct: data.correct,
      }
      fetchPredictionStats()
      // Push notificación inmediata
      const matchId = liveGame.value?.match_id || ''
      fetchWorstChampion(matchId).then(champ => {
        pushNotification({
          id: `pred-${matchId}`,
          icon: data.correct ? '✅' : '❌',
          title: data.correct ? 'Predicción acertada' : 'Predicción fallada',
          body: pickJoke(champ, !!data.correct),
          match_id: matchId,
          correct: !!data.correct,
        })
      })
    } else if (data.error) {
      resolveResult.value = { predicted: '?', actual: '?', correct: false, pending: data.error } as any
    } else if (res.status === 404) {
      resolveResult.value = { predicted: '?', actual: '?', correct: false, pending: 'No se encontró la predicción. ¿Abriste live para esta partida?' } as any
    } else {
      resolveResult.value = { predicted: '?', actual: '?', correct: false, pending: 'La partida aún no ha terminado' } as any
    }
  } catch {
    resolveResult.value = { predicted: '?', actual: '?', correct: false, pending: 'Error de conexión' } as any
  } finally {
    resolving.value = false
  }
}


let lastLiveMatchId: string | null = null

const searchLiveGame = async (forceRefresh = false) => {
  // Si ya habías visto otra partida en esta sesión, fuerza refresh para evitar
  // que la caché de priors (6h TTL) muestre la misma predicción.
  if (!forceRefresh && lastLiveMatchId) {
    forceRefresh = true
  }
  showLiveGame.value = true
  liveLoading.value = true
  liveError.value = ''
  liveGame.value = null
  liveProgress.value = { step: 'Iniciando...', progress: 0, total: 10 }
  liveAbort = false
  fetchPredictionStats()
  try {
    const startRes = await fetch(`${API_BASE}/liveGame/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        game_name: summoner.value.split('#')[0],
        tag_line: summoner.value.split('#')[1],
        force_refresh: forceRefresh,
      }),
    })
    const startData = await startRes.json()
    if (!startRes.ok || startData.error) throw new Error(startData.error || 'Error')
    const jobId = startData.job_id

    // Poll every 600ms
    while (!liveAbort) {
      await new Promise(r => setTimeout(r, 600))
      const pRes = await fetch(`${API_BASE}/liveGame/progress/${jobId}`)
      if (!pRes.ok) continue
      const pData = await pRes.json()
      liveProgress.value = {
        step: pData.step || '',
        progress: pData.progress || 0,
        total: pData.total || 1,
      }
      if (pData.status === 'done') {
        liveGame.value = pData.result
        lastLiveMatchId = pData.result?.match_id || null
        return
      }
      if (pData.status === 'error') {
        throw new Error(pData.error || 'Error procesando partida')
      }
    }
  } catch (err) {
    liveError.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    liveLoading.value = false
  }
}

const closeLiveGame = () => {
  liveAbort = true
  // Intenta resolver la predicción en background al cerrar (si no se hizo ya)
  if (liveGame.value?.match_id && liveGame.value?.viewer_puuid && !resolveResult.value) {
    const matchId = liveGame.value.match_id
    const viewerPuuid = liveGame.value.viewer_puuid
    fetch(`${API_BASE}/resolvePrediction`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ match_id: matchId, viewer_puuid: viewerPuuid }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.resolved) {
          fetchWorstChampion(matchId).then(champ => {
            pushNotification({
              id: `pred-${matchId}`,
              icon: data.correct ? '✅' : '❌',
              title: data.correct ? 'Predicción acertada' : 'Predicción fallada',
              body: pickJoke(champ, !!data.correct),
              match_id: matchId,
              correct: !!data.correct,
            })
          })
          fetchPredictionStats()
        }
      })
      .catch(() => {})
  }
  showLiveGame.value = false
  liveGame.value = null
  liveError.value = ''
  resolveResult.value = null
}

const refresh = async () => {
  loading.value = true
  scanning.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
    })
    const res = await fetch(`${API_BASE}/getOverview?${params}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error al refrescar')
    await new Promise(r => setTimeout(r, 1500))
    matches.value = data.matches
    tier.value = data.tier ?? ''
    division.value = data.division ?? ''
    hasMore.value = data.has_more ?? false
    currentStart.value = data.matches.length
    alerts.value = data.alerts ?? []
    fetchWatchList()
    fetchBlacklist()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
    scanning.value = false
  }
}

const logout = () => {
  summoner.value = ''
  tier.value = ''
  division.value = ''
  matches.value = []
  hasMore.value = false
  currentStart.value = 0
  alerts.value = []
  watchList.value = []
  formData.value = { gameName: '', tagLine: '' }
  stopGlobalPoller()
  history.replaceState(null, '', window.location.pathname)
}

let loadingFlavorInterval: ReturnType<typeof setInterval> | null = null
watch([loadingDetail, analyticsLoading], ([a, b]) => {
  if (a || b) {
    loadingFlavor.value = LOADING_FLAVORS[Math.floor(Math.random() * LOADING_FLAVORS.length)]
    loadingFlavorInterval = setInterval(() => {
      loadingFlavor.value = LOADING_FLAVORS[Math.floor(Math.random() * LOADING_FLAVORS.length)]
    }, 1800)
  } else if (loadingFlavorInterval) {
    clearInterval(loadingFlavorInterval)
    loadingFlavorInterval = null
  }
})

// tierColor / tumorColor / tumorLabel importados de overviewConstants.ts (alias)
const tierColor = TIER_COLORS

const delta = (val: number, avg: number, higherIsBetter = true) => {
  const d = val - avg
  const positive = d > 0
  const better = higherIsBetter ? positive : !positive
  const sign = positive ? '+' : ''
  return { text: `${sign}${Math.round(d)}`, better }
}
</script>

<style scoped>
@keyframes fade {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade {
  animation: fade 0.5s ease forwards;
}

/* X-Ray overlay */
.xray-overlay {
  background: rgba(0, 4, 10, 0.97);
  backdrop-filter: blur(2px);
}

/* CRT scanlines overlay */
.xray-scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 255, 255, 0.03) 0px,
    rgba(0, 255, 255, 0.03) 1px,
    transparent 2px,
    transparent 4px
  );
  pointer-events: none;
  z-index: 2;
  mix-blend-mode: screen;
}

/* TV noise */
@keyframes noiseShift {
  0%   { transform: translate(0, 0); }
  10%  { transform: translate(-2%, -1%); }
  20%  { transform: translate(1%, 2%); }
  30%  { transform: translate(-1%, 1%); }
  40%  { transform: translate(2%, -2%); }
  50%  { transform: translate(-2%, 1%); }
  60%  { transform: translate(1%, -1%); }
  70%  { transform: translate(-1%, 2%); }
  80%  { transform: translate(2%, 1%); }
  90%  { transform: translate(-1%, -2%); }
  100% { transform: translate(0, 0); }
}
.xray-noise {
  position: absolute;
  inset: -5%;
  background-image:
    radial-gradient(circle, rgba(0, 255, 255, 0.15) 1px, transparent 1px),
    radial-gradient(circle, rgba(255, 255, 255, 0.08) 1px, transparent 1px);
  background-size: 3px 3px, 5px 5px;
  background-position: 0 0, 1px 1px;
  opacity: 0.35;
  animation: noiseShift 0.15s steps(6) infinite;
  pointer-events: none;
  z-index: 1;
  mix-blend-mode: screen;
}

/* Floating particles (cancer cells) */
@keyframes floatUp {
  0%   { transform: translateY(100vh) scale(0.4); opacity: 0; }
  15%  { opacity: 0.7; }
  85%  { opacity: 0.5; }
  100% { transform: translateY(-20vh) scale(1); opacity: 0; }
}
.xray-particle {
  position: absolute;
  bottom: 0;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0, 255, 255, 0.9), rgba(0, 255, 255, 0));
  animation: floatUp 4s linear infinite;
  z-index: 2;
  box-shadow: 0 0 8px rgba(0, 255, 255, 0.5);
  pointer-events: none;
}

/* Glitch text */
@keyframes glitchX {
  0%, 100% { transform: translate(0); }
  20% { transform: translate(-2px, 1px); }
  40% { transform: translate(2px, -1px); }
  60% { transform: translate(-1px, 2px); }
  80% { transform: translate(1px, -2px); }
}
.glitch {
  position: relative;
  animation: glitchX 2.5s infinite;
}
.glitch::before,
.glitch::after {
  content: attr(data-text);
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.glitch::before {
  color: rgba(255, 0, 80, 0.7);
  transform: translate(-2px, 0);
  mix-blend-mode: screen;
  clip-path: polygon(0 0, 100% 0, 100% 45%, 0 45%);
  animation: glitchX 1.6s infinite reverse;
}
.glitch::after {
  color: rgba(0, 200, 255, 0.75);
  transform: translate(2px, 0);
  mix-blend-mode: screen;
  clip-path: polygon(0 55%, 100% 55%, 100% 100%, 0 100%);
  animation: glitchX 2.1s infinite;
}

/* Scanning beam */
@keyframes scan {
  0%   { top: -4px; }
  100% { top: 100%; }
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.9), transparent);
  animation: scan 2s linear infinite;
  z-index: 1;
}

.scan-line-glow {
  position: absolute;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(to bottom, transparent, rgba(0, 255, 255, 0.06), transparent);
  animation: scan 2s linear infinite;
  z-index: 1;
  margin-top: -40px;
}

/* Dots pulsing */
@keyframes dotPulse {
  0%, 100% { opacity: 0.2; transform: scale(0.8); }
  50%       { opacity: 1;   transform: scale(1.2); }
}
.xray-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(0, 255, 255, 0.8);
  animation: dotPulse 0.9s ease-in-out infinite;
}

/* Flicker effect on text */
@keyframes flicker {
  0%, 97%, 100% { opacity: 1; }
  98%           { opacity: 0.4; }
  99%           { opacity: 0.9; }
}
.xray-title {
  animation: flicker 4s infinite;
  text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
}
.xray-name {
  text-shadow: 0 0 12px rgba(0, 200, 255, 0.4);
}
.xray-label {
  letter-spacing: 0.3em;
}

/* Corner marks */
.corner {
  position: absolute;
  width: 24px;
  height: 24px;
  border-color: rgba(0, 255, 255, 0.3);
  border-style: solid;
}
.corner-tl { top: 20px; left: 20px;  border-width: 2px 0 0 2px; }
.corner-tr { top: 20px; right: 20px; border-width: 2px 2px 0 0; }
.corner-bl { bottom: 20px; left: 20px;  border-width: 0 0 2px 2px; }
.corner-br { bottom: 20px; right: 20px; border-width: 0 2px 2px 0; }

@keyframes spinSlow {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
.animate-spin-slow {
  display: inline-block;
  animation: spinSlow 4s linear infinite;
}

/* Transition */
.xray-enter-active { transition: opacity 0.3s ease; }
.xray-leave-active { transition: opacity 0.6s ease; }
.xray-enter-from, .xray-leave-to { opacity: 0; }

/* Skeleton shimmer */
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.shimmer {
  background-image: linear-gradient(
    90deg,
    rgba(255,255,255,0.04) 0%,
    rgba(255,255,255,0.12) 50%,
    rgba(255,255,255,0.04) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

/* Excuse toast transition: slide+fade, salida más larga */
.excuse-enter-active { transition: opacity 0.35s ease, transform 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.4); }
.excuse-leave-active { transition: opacity 0.7s ease, transform 0.7s ease; }
.excuse-enter-from   { opacity: 0; transform: translateX(30px) scale(0.9); }
.excuse-leave-to     { opacity: 0; transform: translateX(30px) scale(0.95); }

/* Modal transition */
.modal-enter-active { transition: opacity 0.2s ease; }
.modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
