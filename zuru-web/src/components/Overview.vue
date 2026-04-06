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
          <button @click="searchLiveGame" :disabled="liveLoading"
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
                <p class="text-white text-xs font-bold truncate">{{ match.worst.nombre }}</p>
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
          <div class="rounded-2xl overflow-hidden border border-red-500/30 shadow-2xl shadow-red-900/30 mb-3">
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
          </div>

          <!-- #2-5 compact rows -->
          <div class="space-y-2">
            <div v-for="(tumor, i) in topTumores.slice(1)" :key="tumor.nombre"
              class="flex items-center gap-3 bg-black/30 rounded-xl border border-white/10 px-3 py-2.5 hover:border-red-500/20 transition">
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
            </div>
          </div>
        </div>

        <!-- Global leaderboard tab -->
        <div v-if="sidebarTab === 'global'" class="bg-black/30 rounded-2xl border border-[#c89b3c]/20 overflow-hidden">
          <div class="px-4 py-3 border-b border-white/10">
            <p class="text-[#c89b3c] text-[10px] font-mono tracking-widest font-bold">LEADERBOARD GLOBAL · PEORES JUGADORES</p>
          </div>
          <div v-if="leaderboard.length" class="divide-y divide-white/5">
            <div v-for="entry in leaderboard" :key="entry.nombre"
              class="flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 transition">
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
            </div>
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
      <div v-if="selectedMatchId" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click.self="closeMatchDetail">
        <div class="bg-[#0d1b2a] border border-white/15 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">

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
            <!-- Tumor prediction vs actual -->
            <div class="grid grid-cols-3 gap-3 items-center bg-black/30 border border-white/10 rounded-xl p-3">
              <div class="text-center">
                <p class="text-blue-400 text-[10px] font-mono tracking-widest">AZUL</p>
                <p class="text-blue-200 text-xl font-mono font-black">{{ matchPrediction.blueSum }}</p>
              </div>
              <div class="text-center">
                <p class="text-white/40 text-[9px] font-mono tracking-widest">PREDICCIÓN</p>
                <p class="text-xl">{{ matchPrediction.winner === 'blue' ? '🔵' : matchPrediction.winner === 'red' ? '🔴' : '⚖️' }}</p>
                <p :class="matchPrediction.correct ? 'text-green-400' : matchPrediction.winner === 'tie' ? 'text-white/40' : 'text-red-400'"
                  class="text-[9px] font-mono font-bold mt-0.5">
                  {{ matchPrediction.winner === 'tie' ? 'IGUALADO' : matchPrediction.correct ? '✓ ACERTÓ' : '✗ FALLÓ' }}
                </p>
              </div>
              <div class="text-center">
                <p class="text-red-400 text-[10px] font-mono tracking-widest">ROJO</p>
                <p class="text-red-200 text-xl font-mono font-black">{{ matchPrediction.redSum }}</p>
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
                      <p class="text-white text-xs font-bold truncate">
                        {{ p.nombre === summoner ? '⭐ ' + p.nombre : p.nombre }}
                      </p>
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
                    <div class="text-center shrink-0 w-12 border-l border-white/10 pl-2 ml-1">
                      <p :class="tumorColor(p.tumor_score ?? 0)" class="text-base font-mono font-black leading-none">{{ p.tumor_score ?? '?' }}</p>
                      <p :class="tumorColor(p.tumor_score ?? 0)" class="text-[8px] font-mono font-bold mt-0.5">{{ tumorLabel(p.tumor_score ?? 0) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Live game modal -->
    <Transition name="modal">
      <div v-if="showLiveGame" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click.self="closeLiveGame">
        <div class="bg-[#0d1b2a] border border-red-500/30 rounded-2xl shadow-2xl shadow-red-900/30 w-full max-w-5xl max-h-[90vh] overflow-y-auto">
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

          <div v-if="liveLoading" class="flex flex-col items-center justify-center py-16 gap-3">
            <p class="text-white/40 font-mono text-sm animate-pulse">Analizando 10 jugadores...</p>
            <p class="text-white/20 font-mono text-xs">Esto puede tardar 10-30 segundos</p>
          </div>

          <div v-else-if="liveError" class="py-16 text-center">
            <p class="text-red-400 font-mono text-sm">{{ liveError }}</p>
          </div>

          <div v-else-if="liveGame" class="p-6">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">
              Tumor score promedio basado en últimas rankeds de cada jugador
            </p>

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

            <!-- Win prediction -->
            <div class="grid grid-cols-3 gap-3 mb-4 items-center">
              <div class="bg-blue-950/40 border rounded-xl px-4 py-3 text-center"
                :class="livePrediction.winner === 'blue' ? 'border-blue-400/70 shadow-lg shadow-blue-500/20' : 'border-blue-500/20'">
                <p class="text-blue-400 text-[10px] font-mono tracking-widest">EQUIPO AZUL</p>
                <p class="text-blue-200 text-2xl font-mono font-black mt-1">{{ livePrediction.blueSum }}</p>
                <p class="text-blue-300/60 text-[9px] font-mono">tumor total</p>
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
                <p class="text-red-200 text-2xl font-mono font-black mt-1">{{ livePrediction.redSum }}</p>
                <p class="text-red-300/60 text-[9px] font-mono">tumor total</p>
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

            <div class="grid grid-cols-2 gap-4">
              <!-- Blue team -->
              <div>
                <p class="text-blue-400 text-[11px] font-mono font-bold mb-2 tracking-widest">EQUIPO AZUL</p>
                <div class="space-y-2">
                  <div v-for="p in liveGame.players.filter(x => x.team_id === 100)" :key="p.puuid"
                    :class="p.is_me ? 'border-[#c89b3c]/60 bg-[#c89b3c]/5' : 'border-white/10'"
                    class="flex items-center gap-3 bg-black/30 border rounded-xl p-3">
                    <img v-if="champData[String(p.champion_id)]"
                      :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${champData[String(p.champion_id)]}.png`"
                      class="w-12 h-12 rounded-lg border border-white/20" />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <span v-if="p.is_watched" title="En tu watch list" class="text-base">💀</span>
                        <p class="text-white text-sm font-mono truncate" :class="p.is_watched ? 'text-red-300' : ''">{{ p.nombre }}{{ p.is_me ? ' (TÚ)' : '' }}</p>
                        <span v-if="p.is_main" class="text-[9px] font-mono font-bold bg-purple-500/20 border border-purple-400/40 text-purple-300 px-1.5 py-0.5 rounded">🎯 MAIN</span>
                        <span v-if="p.is_tilted" title="Tilteado: últimas 3 partidas muy malas"
                          class="text-[9px] font-mono font-bold bg-orange-500/20 border border-orange-400/40 text-orange-300 px-1.5 py-0.5 rounded animate-pulse">🔥 TILT</span>
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
                      <p :class="tumorColor(p.avg_tumor_score ?? 0)" class="text-2xl font-mono font-bold leading-none">
                        {{ p.avg_tumor_score ?? '?' }}
                      </p>
                      <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ tumorLabel(p.avg_tumor_score ?? 0) }}</p>
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
                    <img v-if="champData[String(p.champion_id)]"
                      :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${champData[String(p.champion_id)]}.png`"
                      class="w-12 h-12 rounded-lg border border-white/20" />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <span v-if="p.is_watched" title="En tu watch list" class="text-base">💀</span>
                        <p class="text-white text-sm font-mono truncate" :class="p.is_watched ? 'text-red-300' : ''">{{ p.nombre }}{{ p.is_me ? ' (TÚ)' : '' }}</p>
                        <span v-if="p.is_main" class="text-[9px] font-mono font-bold bg-purple-500/20 border border-purple-400/40 text-purple-300 px-1.5 py-0.5 rounded">🎯 MAIN</span>
                        <span v-if="p.is_tilted" title="Tilteado: últimas 3 partidas muy malas"
                          class="text-[9px] font-mono font-bold bg-orange-500/20 border border-orange-400/40 text-orange-300 px-1.5 py-0.5 rounded animate-pulse">🔥 TILT</span>
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
                      <p :class="tumorColor(p.avg_tumor_score ?? 0)" class="text-2xl font-mono font-bold leading-none">
                        {{ p.avg_tumor_score ?? '?' }}
                      </p>
                      <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ tumorLabel(p.avg_tumor_score ?? 0) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Excuse toast -->
    <Transition name="modal">
      <div v-if="excuseText" class="fixed top-6 right-6 z-[60] max-w-sm animate-fade">
        <div class="bg-gradient-to-br from-yellow-900/90 to-amber-950/90 border border-yellow-500/50 rounded-xl shadow-2xl p-4 backdrop-blur">
          <div class="flex items-start gap-3">
            <span class="text-2xl">🗣</span>
            <div class="flex-1">
              <p class="text-yellow-300 text-[10px] font-mono tracking-widest mb-1">EXCUSA OFICIAL</p>
              <p class="text-yellow-100 font-mono text-sm leading-snug">{{ excuseText }}</p>
              <div class="flex gap-2 mt-3">
                <button @click="rollExcuse" class="text-[10px] font-mono px-2 py-1 border border-yellow-500/30 text-yellow-300 rounded hover:border-yellow-500/60">🎲 Otra</button>
                <button @click="excuseText = ''" class="text-[10px] font-mono px-2 py-1 border border-white/10 text-white/40 rounded hover:text-white/70">Cerrar</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Analytics modal -->
    <Transition name="modal">
      <div v-if="showAnalytics" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click.self="closeAnalytics">
        <div class="bg-[#0d1b2a] border border-purple-500/30 rounded-2xl shadow-2xl shadow-purple-900/30 w-full max-w-5xl max-h-[92vh] overflow-y-auto">
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
          <div v-else-if="analyticsData" class="p-6 space-y-8">

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
                <div class="flex items-end gap-1 h-32">
                  <div v-for="h in analyticsData.hour_stats" :key="h.hour"
                    class="flex-1 flex flex-col items-center gap-1 group relative">
                    <div class="w-full rounded-t transition"
                      :class="h.winrate >= 60 ? 'bg-green-500/60' : h.winrate >= 50 ? 'bg-yellow-500/60' : 'bg-red-500/60'"
                      :style="{ height: `${Math.max(6, h.avg_tumor * 1.2)}%` }"></div>
                    <span class="text-white/40 text-[9px] font-mono">{{ String(h.hour).padStart(2, '0') }}h</span>
                    <div class="hidden group-hover:block absolute bottom-full mb-1 bg-black/90 border border-white/20 rounded px-2 py-1 text-[9px] font-mono text-white whitespace-nowrap z-10">
                      {{ h.games }}g · {{ h.winrate }}% WR · tumor {{ h.avg_tumor }}
                    </div>
                  </div>
                </div>
                <p class="text-white/30 text-[9px] font-mono mt-2">Altura = tumor medio · Color = winrate</p>
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
    </Transition>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, onMounted, onUnmounted } from 'vue'

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
const theme = inject<ReturnType<typeof computed>>('theme')!

const ddragonVersion = ref('15.1.1') // fallback; overwritten on mount

const champData = ref<Record<string, string>>({})

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
  })
  .catch(() => {})

const formData = ref({ gameName: '', tagLine: '' })
const summoner = ref('')
const tier = ref('')
const division = ref('')
const matches = ref<MatchOverview[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const scanning = ref(false)

const LOADING_FLAVORS = [
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
const loadingFlavor = ref(LOADING_FLAVORS[0])

const EXCUSE_STARTERS = [
  'Perdí porque',
  'No fue mi culpa,',
  'La realidad es que',
  'Obviamente',
  'Claramente',
]
const EXCUSE_REASONS = [
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
const EXCUSE_ENDINGS = [
  'y además hacía mucho calor.',
  'era imposible ganar.',
  'y los dioses no me querían.',
  'así cualquiera pierde.',
  'y por eso bajé de elo.',
  'pero bueno, GG WP.',
  'y yo era el único intentándolo.',
  '— no tenía sentido insistir.',
]
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
})

const excuseText = ref('')
const rollExcuse = () => {
  const s = EXCUSE_STARTERS[Math.floor(Math.random() * EXCUSE_STARTERS.length)]
  const r1 = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
  let r2 = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
  while (r2 === r1) r2 = EXCUSE_REASONS[Math.floor(Math.random() * EXCUSE_REASONS.length)]
  const e = EXCUSE_ENDINGS[Math.floor(Math.random() * EXCUSE_ENDINGS.length)]
  excuseText.value = `${s} ${r1}, también ${r2}, ${e}`
}


const SCAN_MESSAGES = [
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
const scanMessage = ref(SCAN_MESSAGES[0])
let scanInterval: ReturnType<typeof setInterval> | null = null

watch(scanning, (v) => {
  if (v) {
    let i = 0
    scanMessage.value = SCAN_MESSAGES[Math.floor(Math.random() * SCAN_MESSAGES.length)]
    scanInterval = setInterval(() => {
      i = (i + 1) % SCAN_MESSAGES.length
      scanMessage.value = SCAN_MESSAGES[Math.floor(Math.random() * SCAN_MESSAGES.length)]
    }, 800)
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
    const res = await fetch(`http://localhost:5000/matchDetail/${matchId}?viewer_tier=${encodeURIComponent(tier.value || 'GOLD')}`)
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
    const res = await fetch('http://localhost:5000/recentSummoners')
    recentSummoners.value = await res.json()
  } catch {}
}

const fetchLeaderboard = async () => {
  try {
    const res = await fetch('http://localhost:5000/leaderboard')
    leaderboard.value = await res.json()
  } catch {}
}

const fetchSavedAccounts = async () => {
  try {
    const res = await fetch('http://localhost:5000/savedAccounts')
    savedAccounts.value = await res.json()
  } catch {}
}

const isSaved = computed(() => summoner.value && savedAccounts.value.includes(summoner.value))

const toggleSaveAccount = async () => {
  const method = isSaved.value ? 'DELETE' : 'POST'
  try {
    const res = await fetch('http://localhost:5000/savedAccounts', {
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
    const res = await fetch(`http://localhost:5000/watchList?summoner=${encodeURIComponent(summoner.value)}`)
    watchList.value = await res.json()
  } catch {}
}

const isWatched = (nombre: string) => watchList.value.includes(nombre)

const toggleWatch = async (nombre: string) => {
  const method = isWatched(nombre) ? 'DELETE' : 'POST'
  try {
    const res = await fetch('http://localhost:5000/watchList', {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: summoner.value, tumor: nombre })
    })
    watchList.value = await res.json()
  } catch {}
}

const saveRecent = async (name: string) => {
  try {
    await fetch('http://localhost:5000/recentSummoners', {
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

    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
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

    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
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
  recent_losses: number
  recent_avg_tumor: number
  mastery_points: number
  mastery_level: number
  estimated_games: number
  is_me: boolean
  is_watched: boolean
  is_blacklisted: boolean
  champion_name: string
  duo_group?: string
  duo_size?: number
}
interface LiveGame {
  game_id: number
  queue_id: number
  players: LivePlayer[]
}

interface EvolutionPoint { date: number; tumor: number; win: boolean; champion: string; kda: number }
interface HourStat { hour: number; games: number; winrate: number; avg_tumor: number }
interface WeekStat { games: number; wins: number; winrate: number; avg_tumor: number }
interface DuoStat { puuid: string; nombre: string; games: number; wins: number; winrate: number; top_champion: string }
interface RoleComboStat { my_role: string; other_role: string; games: number; wins: number; winrate: number }
interface AnalyticsData {
  summoner: string
  tier: string
  total_matches: number
  evolution: EvolutionPoint[]
  hour_stats: HourStat[]
  week_stats: { this: WeekStat | null; last: WeekStat | null }
  duo_stats: DuoStat[]
  role_combo_stats: RoleComboStat[]
}

const analyticsData = ref<AnalyticsData | null>(null)
const analyticsLoading = ref(false)
const analyticsError = ref('')
const showAnalytics = ref(false)

const openAnalytics = async () => {
  showAnalytics.value = true
  analyticsLoading.value = true
  analyticsError.value = ''
  analyticsData.value = null
  try {
    const params = new URLSearchParams({
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
      count: '30',
    })
    const res = await fetch(`http://localhost:5000/playerAnalytics?${params}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error')
    analyticsData.value = data
  } catch (err) {
    analyticsError.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    analyticsLoading.value = false
  }
}

const closeAnalytics = () => {
  showAnalytics.value = false
  analyticsData.value = null
  analyticsError.value = ''
}

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
  if (!entry) return { background: 'rgba(255,255,255,0.02)' }
  const hue = entry.winrate >= 50 ? 120 : 0
  const alpha = Math.min(0.6, 0.15 + (Math.abs(entry.winrate - 50) / 50) * 0.5)
  return { background: `hsla(${hue}, 70%, 40%, ${alpha})`, color: 'white' }
}

const heatmapCellText = (myRole: string, otherRole: string) => {
  const entry = analyticsData.value?.role_combo_stats.find(
    r => r.my_role === myRole && r.other_role === otherRole
  )
  if (!entry) return '—'
  return `${entry.winrate}%`
}

const championBlacklist = ref<string[]>([])

const fetchBlacklist = async () => {
  if (!summoner.value) return
  try {
    const res = await fetch(`http://localhost:5000/championBlacklist?summoner=${encodeURIComponent(summoner.value)}`)
    if (res.ok) championBlacklist.value = await res.json()
  } catch {}
}

const toggleBlacklist = async (champion: string) => {
  const method = championBlacklist.value.includes(champion) ? 'DELETE' : 'POST'
  try {
    const res = await fetch('http://localhost:5000/championBlacklist', {
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
    const res = await fetch('http://localhost:5000/predictionStats')
    if (res.ok) predictionStats.value = await res.json()
  } catch {}
}

const ROLE_ORDER = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
const ROLE_LABEL: Record<string, string> = {
  TOP: 'TOP', JUNGLE: 'JNG', MIDDLE: 'MID', BOTTOM: 'ADC', UTILITY: 'SUP'
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
  if (!matchDetail.value) return { blueSum: 0, redSum: 0, winner: 'tie', correct: false }
  const blueSum = matchDetail.value.team_blue.reduce((s: number, p: any) => s + (p.tumor_score ?? 0), 0)
  const redSum = matchDetail.value.team_red.reduce((s: number, p: any) => s + (p.tumor_score ?? 0), 0)
  const diff = Math.abs(blueSum - redSum)
  let winner: 'blue' | 'red' | 'tie' = 'tie'
  if (diff >= 5) winner = blueSum < redSum ? 'blue' : 'red'
  const actualBlueWon = matchDetail.value.blue_win
  const correct = (winner === 'blue' && actualBlueWon) || (winner === 'red' && !actualBlueWon)
  return { blueSum, redSum, winner, correct }
})

const livePrediction = computed(() => {
  if (!liveGame.value) return { blueSum: 0, redSum: 0, winner: 'tie', confidence: 0 }
  const blue = liveGame.value.players.filter(p => p.team_id === 100)
  const red = liveGame.value.players.filter(p => p.team_id === 200)
  const sum = (arr: LivePlayer[]) => arr.reduce((s, p) => s + (p.avg_tumor_score ?? 0), 0)
  const blueSum = sum(blue)
  const redSum = sum(red)
  const diff = Math.abs(blueSum - redSum)
  const total = blueSum + redSum
  const confidence = total > 0 ? Math.min(99, Math.round((diff / total) * 200)) : 0
  let winner: 'blue' | 'red' | 'tie' = 'tie'
  if (diff >= 5) winner = blueSum < redSum ? 'blue' : 'red'
  return { blueSum, redSum, winner, confidence }
})

const liveLoading = ref(false)
const liveError = ref('')
const showLiveGame = ref(false)

const searchLiveGame = async () => {
  showLiveGame.value = true
  liveLoading.value = true
  liveError.value = ''
  liveGame.value = null
  fetchPredictionStats()
  try {
    const params = new URLSearchParams({
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
    })
    const res = await fetch(`http://localhost:5000/liveGame?${params}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error')
    liveGame.value = data
  } catch (err) {
    liveError.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    liveLoading.value = false
  }
}

const closeLiveGame = () => {
  showLiveGame.value = false
  liveGame.value = null
  liveError.value = ''
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
    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
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

const tierColor: Record<string, string> = {
  IRON: 'text-[#8a7462]', BRONZE: 'text-[#a0522d]', SILVER: 'text-[#a0a9b0]',
  GOLD: 'text-[#c89b3c]', PLATINUM: 'text-[#4e9e8a]', EMERALD: 'text-[#2ecc71]',
  DIAMOND: 'text-[#7ec8e3]', MASTER: 'text-[#c45cff]', GRANDMASTER: 'text-[#ff4444]',
  CHALLENGER: 'text-[#f4c542]', UNRANKED: 'text-white/40',
}

const tumorColor = (score: number) => {
  if (score >= 75) return 'text-red-500'
  if (score >= 50) return 'text-orange-400'
  if (score >= 25) return 'text-yellow-400'
  return 'text-green-400'
}

const tumorLabel = (score: number) => {
  if (score >= 75) return '☢ NUCLEAR'
  if (score >= 50) return '☣ TUMOR'
  if (score >= 25) return '⚠ SUS'
  return '✓ DECENTE'
}

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

/* Modal transition */
.modal-enter-active { transition: opacity 0.2s ease; }
.modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
