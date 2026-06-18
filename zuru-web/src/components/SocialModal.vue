<template>
  <Teleport to="body">
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center overflow-y-auto p-4 pt-[8vh] sm:pt-4"
      @click.self="emit('close')">
      <div class="bg-[#0d1b2a] border border-yellow-500/30 rounded-2xl shadow-2xl shadow-yellow-900/30 w-full max-w-3xl max-h-[88vh] flex flex-col">
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <p class="text-yellow-200 font-mono font-bold flex items-center gap-2">
            <span>🌐</span><span>{{ $t('social.title') }}</span>
          </p>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <!-- Tabs -->
        <div class="flex gap-1 px-5 py-2 border-b border-white/10">
          <button v-for="tab in tabs" :key="tab.key" @click="active = tab.key"
            :class="active === tab.key
              ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50'
              : 'text-white/40 border-transparent hover:text-white/70'"
            class="text-xs font-mono px-3 py-1.5 rounded border transition">
            {{ tab.label }}
          </button>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-y-auto p-5">
          <!-- HOT BETS -->
          <div v-if="active === 'hot'">
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-3">{{ $t('social.open_bets_caption') }}</p>
            <p v-if="!openBets.length" class="text-white/30 text-sm font-mono text-center py-8">
              {{ $t('social.no_open_bets') }}
            </p>
            <div class="space-y-2">
              <div v-for="b in openBets" :key="b.id"
                class="bg-black/30 border border-white/10 hover:border-yellow-500/40 transition rounded-xl p-3 flex items-center gap-3">
                <div class="text-2xl">{{ b.creator_side === 'blue' ? '🔵' : '🔴' }}</div>
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">
                    <span class="font-bold">{{ b.creator?.username || $t('social.anonymous') }}</span>
                    {{ $t('social.bets_amount') }} <span class="text-yellow-300 font-bold">{{ b.amount }} TC</span>
                  </p>
                  <p class="text-white/40 text-[10px] font-mono">{{ $t('social.match_label') }} {{ b.match_id }}</p>
                </div>
                <button @click="onAccept(b)"
                  class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                  {{ $t('common.accept') }} {{ b.creator_side === 'blue' ? '🔴' : '🔵' }}
                </button>
              </div>
            </div>
          </div>

          <!-- LEADERBOARDS -->
          <div v-else-if="active === 'leaderboards'">
            <div class="flex gap-1 mb-3">
              <button v-for="lk in leaderboardKinds" :key="lk.key" @click="lbKind = lk.key; loadLeaderboard()"
                :class="lbKind === lk.key
                  ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50'
                  : 'text-white/40 border-transparent hover:text-white/70'"
                class="text-[10px] font-mono px-2 py-1 rounded border transition">
                {{ lk.label }}
              </button>
            </div>
            <div v-if="!leaderboard.length" class="text-white/30 text-sm font-mono text-center py-8">
              {{ $t('social.no_data') }}
            </div>
            <div v-else class="space-y-1">
              <div v-for="(u, i) in leaderboard" :key="u.user_id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex items-center gap-3">
                <span class="font-mono font-bold w-6 text-center"
                  :class="i < 3 ? 'text-[#c89b3c]' : 'text-white/30'">
                  {{ i < 3 ? ['🥇','🥈','🥉'][i] : '#' + (i + 1) }}
                </span>
                <Avatar :discord-id="u.discord_id" :avatar="u.avatar" :username="u.username" size="md" />
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">{{ u.username }}</p>
                  <p v-if="u.riot_id" class="text-[#c89b3c] text-[10px] font-mono">{{ u.riot_id }}</p>
                </div>
                <div class="text-right text-xs font-mono">
                  <p v-if="lbKind === 'currency'" class="text-yellow-300 font-bold">{{ u.currency }} TC</p>
                  <p v-else-if="lbKind === 'bets'" class="text-yellow-300 font-bold">
                    {{ u.won_count }} W · +{{ u.net_won }} TC
                  </p>
                  <p v-else-if="lbKind === 'accuracy'" class="text-green-400 font-bold">
                    {{ u.accuracy }}% · {{ u.hits }}/{{ u.total }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- CLUSTERS -->
          <div v-else-if="active === 'clusters'">
            <div v-if="clustersLoading" class="text-white/30 text-sm font-mono text-center py-8">
              {{ $t('social.calculating') }}
            </div>
            <div v-else-if="!clusters.length" class="text-white/30 text-sm font-mono text-center py-8">
              {{ $t('social.no_cluster_data') }}
            </div>
            <div v-else class="space-y-4">
              <div v-for="c in clusters" :key="c.id"
                class="relative rounded-2xl overflow-hidden border-2 transition hover:scale-[1.01]"
                :style="{
                  borderColor: (c.color || '#64748b') + '99',
                  background: `linear-gradient(135deg, ${c.color || '#64748b'}22 0%, transparent 50%, ${c.color || '#64748b'}11 100%)`,
                  boxShadow: `0 0 30px -10px ${c.color || '#64748b'}66`
                }">
                <!-- Header con emoji enorme + nombre del archetype -->
                <div class="flex items-center gap-3 p-4 border-b border-white/10">
                  <div class="text-5xl shrink-0 drop-shadow-lg" style="filter: saturate(1.3)">
                    {{ c.emoji }}
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-white font-mono font-black text-xl tracking-wide" :style="{ color: c.color || '#e2e8f0' }">
                      {{ c.name }}
                    </p>
                    <p class="text-white/60 text-[11px] font-mono italic mt-0.5 leading-tight">
                      {{ c.description || '' }}
                    </p>
                  </div>
                  <div class="shrink-0 text-right">
                    <p class="text-2xl font-mono font-black" :style="{ color: c.color || '#e2e8f0' }">{{ c.size }}</p>
                    <p class="text-white/40 text-[9px] font-mono uppercase tracking-widest">jugadores</p>
                  </div>
                </div>

                <!-- Stats con barras visuales -->
                <div class="p-4 space-y-2.5">
                  <div>
                    <div class="flex items-center justify-between text-[10px] font-mono mb-1">
                      <span class="text-white/50">Tumor prior</span>
                      <span class="text-yellow-300 font-bold">{{ c.centroid.avg_prior }}</span>
                    </div>
                    <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div class="h-full rounded-full transition-all"
                        :style="{
                          width: Math.min(100, c.centroid.avg_prior) + '%',
                          background: `linear-gradient(90deg, #22c55e 0%, #eab308 50%, #ef4444 100%)`
                        }"></div>
                    </div>
                  </div>
                  <div>
                    <div class="flex items-center justify-between text-[10px] font-mono mb-1">
                      <span class="text-white/50">Tumor reciente</span>
                      <span class="text-yellow-300 font-bold">{{ c.centroid.avg_recent }}</span>
                    </div>
                    <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div class="h-full rounded-full transition-all"
                        :style="{
                          width: Math.min(100, c.centroid.avg_recent) + '%',
                          background: `linear-gradient(90deg, #22c55e 0%, #eab308 50%, #ef4444 100%)`
                        }"></div>
                    </div>
                  </div>
                  <div>
                    <div class="flex items-center justify-between text-[10px] font-mono mb-1">
                      <span class="text-white/50">Winrate</span>
                      <span :class="c.centroid.win_rate >= 55 ? 'text-green-400' : c.centroid.win_rate <= 45 ? 'text-red-400' : 'text-yellow-300'"
                        class="font-bold">{{ c.centroid.win_rate }}%</span>
                    </div>
                    <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                      <div class="h-full rounded-full bg-green-500/70 transition-all"
                        :style="{ width: c.centroid.win_rate + '%' }"></div>
                    </div>
                  </div>
                  <div class="grid grid-cols-2 gap-3 text-[10px] font-mono pt-1">
                    <p class="text-white/40">
                      🌋 Tilteados: <span class="text-orange-400 font-bold">{{ c.centroid.tilt_frac }}%</span>
                    </p>
                    <p class="text-white/40">
                      🔥 Hot streak: <span class="text-emerald-400 font-bold">{{ c.centroid.streak_frac }}%</span>
                    </p>
                  </div>
                </div>

                <!-- Ejemplos -->
                <div v-if="c.samples.length" class="p-4 pt-2 border-t border-white/5 bg-black/20">
                  <p class="text-white/30 text-[9px] font-mono tracking-widest mb-2">{{ $t('social.cluster_examples') }}</p>
                  <div class="space-y-1">
                    <div v-for="(s, i) in (c.samples as any[])" :key="i"
                      class="flex items-center gap-2 text-[10px] font-mono py-0.5">
                      <span class="text-white/30 w-4">{{ Number(i) + 1 }}.</span>
                      <span class="text-white/70 truncate flex-1">
                        <span class="text-white/40">{{ s.tier || 'UNRANKED' }}</span>
                        <span class="text-white/20"> · </span>
                        <span class="text-white/50">{{ ROLE_LABEL[s.role] || (s.role ? s.role.slice(0,3) : '?') }}</span>
                      </span>
                      <span class="text-yellow-300 w-7 text-right font-bold">{{ s.prior_tumor }}</span>
                      <span class="text-white/30">·</span>
                      <span class="text-green-400 w-10 text-right">{{ s.win_rate }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- CHALLENGES (1v1) -->
          <div v-else-if="active === 'challenges'">
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-3">
              {{ $t('social.challenges_intro') }}
            </p>

            <!-- Crear challenge: cards visuales para cada formato -->
            <div class="bg-gradient-to-br from-purple-900/20 via-black/30 to-cyan-900/20 border border-white/10 rounded-xl p-3 mb-4">
              <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">{{ $t('social.create') }} · ELIGE FORMATO</p>

              <!-- Cards de formato -->
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <button v-for="fmt in CHALLENGE_FORMATS" :key="fmt.key"
                  @click="newChallengeFormat = fmt.key as any"
                  class="relative p-2 rounded-lg border-2 transition transform hover:scale-105"
                  :class="newChallengeFormat === fmt.key
                    ? 'bg-black/40 shadow-lg'
                    : 'bg-black/20 border-white/10 opacity-60 hover:opacity-100'"
                  :style="newChallengeFormat === fmt.key
                    ? { borderColor: fmt.color, boxShadow: `0 0 20px -5px ${fmt.color}80` }
                    : {}">
                  <div class="text-3xl">{{ fmt.emoji }}</div>
                  <p class="text-[11px] font-mono font-bold mt-1"
                    :style="newChallengeFormat === fmt.key ? { color: fmt.color } : { color: 'rgba(255,255,255,0.7)' }">
                    {{ fmt.name }}
                  </p>
                  <p class="text-white/30 text-[8px] font-mono mt-0.5">⏱ {{ fmt.duration }}</p>
                </button>
              </div>

              <!-- Descripción del formato -->
              <p class="text-white/60 text-[10px] font-mono mb-3 italic leading-relaxed px-1">
                {{ formatMeta(newChallengeFormat).desc }}
              </p>

              <!-- Inputs: stat (solo single) + rival picker + stake -->
              <div v-if="newChallengeFormat === 'single'" class="mb-2">
                <label class="text-white/40 text-[9px] font-mono tracking-widest">ESTADÍSTICA A COMPARAR</label>
                <select v-model="newChallengeStat"
                  class="w-full bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none mt-1">
                  <option value="kda">📊 KDA</option>
                  <option value="kills">🗡 Kills</option>
                  <option value="deaths">💀 Deaths ({{ $t('social.lower_wins_label') }})</option>
                  <option value="assists">🤝 Assists</option>
                  <option value="cs">🌾 CS</option>
                  <option value="gold">💰 Gold</option>
                  <option value="damage">💥 Damage</option>
                  <option value="tumor_score">☢ Tumor Score</option>
                </select>
              </div>

              <!-- Rival picker -->
              <div class="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <label class="text-white/40 text-[9px] font-mono tracking-widest">RIVAL</label>
                  <select v-model="newChallengeRival"
                    class="w-full bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none mt-1">
                    <option :value="null">🌐 Cualquiera (share code)</option>
                    <option v-for="f in friends" :key="f.id || f.user_id" :value="f.id || f.user_id">
                      👤 {{ f.username }}
                    </option>
                  </select>
                </div>
                <div>
                  <label class="text-white/40 text-[9px] font-mono tracking-widest">STAKE TC</label>
                  <input type="number" v-model.number="newChallengeAmount" :min="10"
                    class="w-full bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none mt-1"
                    :placeholder="$t('social.stake_placeholder')" />
                </div>
              </div>

              <button @click="onCreateChallenge" :disabled="!newChallengeAmount || newChallengeAmount <= 0"
                class="w-full font-mono font-bold text-xs px-3 py-2 rounded transition disabled:opacity-30"
                :style="{
                  background: `linear-gradient(135deg, ${formatMeta(newChallengeFormat).color}, ${formatMeta(newChallengeFormat).color}88)`,
                  color: '#0d1b2a',
                  boxShadow: `0 0 15px -5px ${formatMeta(newChallengeFormat).color}`,
                }">
                {{ formatMeta(newChallengeFormat).emoji }} Lanzar {{ formatMeta(newChallengeFormat).name }} · {{ newChallengeAmount }} TC
              </button>
              <p class="text-white/40 text-[9px] font-mono mt-1.5 text-center italic">
                {{ newChallengeRival
                  ? '📨 Directo a tu amigo — sólo él/ella podrá aceptar'
                  : '🌐 Apuesta abierta — aparecerá en el feed público para que cualquiera se una' }}
              </p>
              <p v-if="challengeError" class="text-red-400 text-[10px] font-mono mt-1.5">{{ challengeError }}</p>
            </div>

            <div v-if="challengesLoading" class="text-white/30 text-sm font-mono text-center py-4">
              {{ $t('common.loading') }}
            </div>

            <!-- Mis challenges — vista dinámica con progreso visual -->
            <div v-if="myChallenges.length" class="space-y-3 mb-4">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">{{ $t('social.my_challenges') }}</p>
              <div v-for="c in myChallenges" :key="c.id"
                class="relative bg-black/30 rounded-xl border-2 p-3 overflow-hidden"
                :style="{
                  borderColor: formatMeta(c.format || 'single').color + '55',
                  background: `linear-gradient(135deg, ${formatMeta(c.format || 'single').color}11 0%, transparent 50%)`
                }">

                <!-- Header: emoji + name + share_code + amount + status -->
                <div class="flex items-center gap-2 flex-wrap mb-2">
                  <span class="text-2xl shrink-0">{{ formatMeta(c.format || 'single').emoji }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="font-mono font-bold text-sm"
                      :style="{ color: formatMeta(c.format || 'single').color }">
                      {{ formatMeta(c.format || 'single').name }}
                    </p>
                    <p class="text-white/30 text-[9px] font-mono">{{ c.share_code }} · {{ c.amount }} TC</p>
                  </div>
                  <span class="text-[9px] font-bold px-2 py-0.5 rounded uppercase"
                    :class="c.status === 'open' ? 'bg-yellow-900/40 text-yellow-300'
                          : c.status === 'accepted' ? 'bg-cyan-900/40 text-cyan-300'
                          : c.status === 'resolved' ? 'bg-green-900/40 text-green-300'
                          : 'bg-white/10 text-white/40'">
                    {{ c.status }}
                  </span>
                </div>

                <!-- Players: A vs B -->
                <div class="grid grid-cols-2 gap-2 mb-2">
                  <div class="text-center p-2 rounded bg-cyan-950/30 border border-cyan-500/30">
                    <p class="text-cyan-300 text-[10px] font-mono font-bold truncate"
                      :class="{ 'underline': c.challenger_user_id === myUserId }">
                      {{ c.challenger?.username || '?' }}
                    </p>
                    <p v-if="(c.format === 'streak' || c.format === 'bo3')" class="text-cyan-200 text-2xl font-mono font-black mt-1">
                      {{ c.challenger_wins ?? 0 }}
                    </p>
                    <p v-else-if="c.format === 'tumor_race'" class="text-cyan-200 text-lg font-mono font-black mt-1">
                      ☢ {{ c.challenger_value ?? '?' }}
                    </p>
                    <p v-else class="text-cyan-200 text-lg font-mono font-black mt-1">
                      {{ c.challenger_value ?? '—' }}
                    </p>
                  </div>
                  <div class="text-center p-2 rounded bg-pink-950/30 border border-pink-500/30">
                    <p class="text-pink-300 text-[10px] font-mono font-bold truncate"
                      :class="{ 'underline': c.challenged_user_id === myUserId }">
                      {{ c.challenged?.username || (c.status === 'open' ? '...esperando rival' : '?') }}
                    </p>
                    <p v-if="(c.format === 'streak' || c.format === 'bo3')" class="text-pink-200 text-2xl font-mono font-black mt-1">
                      {{ c.challenged_wins ?? 0 }}
                    </p>
                    <p v-else-if="c.format === 'tumor_race'" class="text-pink-200 text-lg font-mono font-black mt-1">
                      ☢ {{ c.challenged_value ?? '?' }}
                    </p>
                    <p v-else class="text-pink-200 text-lg font-mono font-black mt-1">
                      {{ c.challenged_value ?? '—' }}
                    </p>
                  </div>
                </div>

                <!-- Progress bar para bo3 / streak -->
                <div v-if="(c.format === 'bo3' || c.format === 'streak') && c.matches_required"
                  class="mb-2">
                  <div class="flex items-center justify-between text-[9px] font-mono mb-1">
                    <span class="text-cyan-400">{{ c.challenger_wins ?? 0 }} / {{ c.matches_required }}</span>
                    <span class="text-white/30">{{ c.format === 'streak' ? 'streak actual' : 'target' }}</span>
                    <span class="text-pink-400">{{ c.challenged_wins ?? 0 }} / {{ c.matches_required }}</span>
                  </div>
                  <div class="flex gap-px h-1.5">
                    <div v-for="i in (c.matches_required)" :key="`c${i}`" class="flex-1 rounded-full"
                      :class="(c.challenger_wins ?? 0) >= i ? 'bg-cyan-400' : 'bg-cyan-950/40'"></div>
                    <div class="w-2"></div>
                    <div v-for="i in (c.matches_required)" :key="`d${i}`" class="flex-1 rounded-full"
                      :class="(c.challenged_wins ?? 0) >= i ? 'bg-pink-400' : 'bg-pink-950/40'"></div>
                  </div>
                </div>

                <!-- Time remaining for active challenges -->
                <p v-if="c.status === 'accepted' && c.expires_at" class="text-white/40 text-[9px] font-mono text-center mb-1">
                  ⏳ Expira en {{ humanizeTimeUntil(c.expires_at) }}
                </p>
                <p v-else-if="c.status === 'open'" class="text-white/40 text-[9px] font-mono text-center italic mb-1">
                  Esperando a alguien que acepte...
                </p>

                <!-- Resultado -->
                <p v-if="c.status === 'resolved'" class="text-center text-[11px] font-mono font-bold mt-1"
                  :class="c.winner_user_id === myUserId ? 'text-green-400' : c.winner_user_id ? 'text-red-400' : 'text-white/50'">
                  {{
                    c.winner_user_id === myUserId ? $t('social.challenge_won', { amount: c.amount }) :
                    c.winner_user_id ? $t('social.challenge_lost', { amount: c.amount }) :
                    $t('social.challenge_push')
                  }}
                </p>

                <!-- Submit match (legacy single) -->
                <div v-if="challengeNeedsSubmit(c)" class="flex gap-2 mt-2">
                  <input v-model="matchIdInput" placeholder="EUW1_1234567890"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-[11px] focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onSubmitMatch(c)" :disabled="!matchIdInput.trim() || submittingMatchFor === c.share_code"
                    class="text-[10px] font-mono px-2 py-1 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 text-black font-bold rounded">
                    {{ submittingMatchFor === c.share_code ? '...' : $t('social.submit') }}
                  </button>
                </div>

                <!-- Cancel -->
                <button v-if="c.status === 'open' && c.challenger_user_id === myUserId"
                  @click="onCancelChallenge(c)"
                  class="text-[10px] font-mono px-2 py-1 mt-2 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
                  {{ $t('common.cancel') }}
                </button>
              </div>
            </div>

            <!-- Open challenges feed -->
            <div v-if="openChallenges.length" class="space-y-2">
              <p class="text-white/40 text-[10px] font-mono tracking-widest">🌐 ÚNETE · {{ openChallenges.length }} ABIERTAS</p>
              <div v-for="c in openChallenges" :key="c.id"
                class="rounded-xl border-2 p-2.5 flex items-center gap-3"
                :style="{
                  borderColor: formatMeta(c.format || 'single').color + '66',
                  background: `linear-gradient(135deg, ${formatMeta(c.format || 'single').color}15 0%, transparent 60%)`
                }">
                <span class="text-2xl shrink-0">{{ formatMeta(c.format || 'single').emoji }}</span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1 flex-wrap">
                    <span class="font-mono font-bold text-[11px]"
                      :style="{ color: formatMeta(c.format || 'single').color }">
                      {{ formatMeta(c.format || 'single').name }}
                    </span>
                    <span v-if="c.target_user_id === myUserId"
                      class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-pink-900/60 text-pink-200">
                      📨 PARA TI
                    </span>
                  </div>
                  <p class="text-white/70 text-[11px] font-mono mt-0.5 truncate">
                    <span class="text-cyan-300 font-bold">{{ c.challenger?.username || '?' }}</span>
                    <span v-if="c.format === 'single' && c.stat_type" class="text-white/40"> · {{ c.stat_type }}</span>
                    <span class="text-yellow-300"> · {{ c.amount }} TC</span>
                  </p>
                </div>
                <button @click="onAcceptChallenge(c)"
                  class="text-[10px] font-mono font-bold px-3 py-1.5 rounded shrink-0"
                  :style="{
                    background: formatMeta(c.format || 'single').color,
                    color: '#0d1b2a',
                  }">
                  Unirme
                </button>
              </div>
            </div>

            <div v-if="!myChallenges.length && !openChallenges.length && !challengesLoading"
              class="text-white/30 text-sm font-mono text-center py-4">
              {{ $t('social.no_challenges') }}
            </div>
          </div>

          <!-- BRAVERY -->
          <div v-else-if="active === 'bravery'">
            <BraveryPanel :room-code="null" />
          </div>

          <!-- FRIENDS -->
          <div v-else-if="active === 'friends'">
            <div class="flex gap-2 mb-4">
              <input v-model="friendSearchInput" placeholder="Riot ID (Nombre#TAG)"
                autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false"
                class="flex-1 bg-black/40 border border-white/15 rounded-lg px-3 py-2 text-white font-mono text-sm focus:border-yellow-500/60 focus:outline-none" />
              <button @click="onAddFriend" :disabled="addingFriend"
                class="text-xs font-mono px-3 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 text-black font-bold rounded-lg">
                {{ addingFriend ? '...' : '+ Añadir' }}
              </button>
            </div>
            <p v-if="friendError" class="text-red-400 text-xs font-mono mb-3">{{ friendError }}</p>
            <p v-if="!friends.length" class="text-white/30 text-sm font-mono text-center py-8">
              Aún no tienes amigos. Añade por Riot ID.
            </p>
            <div class="space-y-1">
              <div v-for="f in friends" :key="f.id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex items-center gap-3">
                <Avatar :discord-id="f.other_user?.discord_id" :avatar="f.other_user?.avatar"
                  :username="f.other_user?.username" size="md" />
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">{{ f.other_user?.username || 'Usuario' }}</p>
                  <p class="text-white/40 text-[10px] font-mono">
                    {{ f.status === 'pending' ? (f.direction === 'sent' ? 'Pendiente (enviada)' : 'Te ha invitado') :
                       f.status === 'accepted' ? 'Amigos' :
                       f.status === 'rejected' ? 'Rechazada' : f.status }}
                  </p>
                </div>
                <div class="flex gap-1">
                  <button v-if="f.status === 'pending' && f.direction === 'received'" @click="onAcceptFriend(f.id)"
                    class="text-[10px] font-mono px-2 py-1 bg-green-700 hover:bg-green-600 text-white rounded">
                    Aceptar
                  </button>
                  <button v-if="f.status === 'pending' && f.direction === 'received'" @click="onRejectFriend(f.id)"
                    class="text-[10px] font-mono px-2 py-1 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
                    Rechazar
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- ROOMS -->
          <div v-else-if="active === 'rooms'">
            <!-- VISTA LISTA: cuando no hay currentRoom -->
            <div v-if="!currentRoom" class="space-y-4">
              <!-- Crear + Unirse -->
              <div class="grid grid-cols-2 gap-3">
                <div class="bg-gradient-to-br from-yellow-900/20 to-black/40 border border-yellow-500/30 rounded-xl p-3">
                  <p class="text-yellow-400 text-[10px] font-mono tracking-widest mb-2">+ CREAR SALA</p>
                  <div class="flex gap-2">
                    <input v-model="newRoomName" placeholder="Nombre opcional" maxlength="40"
                      class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none" />
                    <button @click="onCreateRoom"
                      class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                      Crear
                    </button>
                  </div>
                </div>
                <div class="bg-gradient-to-br from-cyan-900/20 to-black/40 border border-cyan-500/30 rounded-xl p-3">
                  <p class="text-cyan-400 text-[10px] font-mono tracking-widest mb-2">→ UNIRSE</p>
                  <div class="flex gap-2">
                    <input v-model="joinCodeInput" placeholder="ABCD12" maxlength="6"
                      class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs uppercase tracking-widest focus:border-cyan-500/60 focus:outline-none" />
                    <button @click="onJoinRoom"
                      class="text-xs font-mono px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded">
                      Entrar
                    </button>
                  </div>
                </div>
              </div>

              <!-- Mis salas -->
              <div>
                <div class="flex items-center justify-between mb-2">
                  <p class="text-white/40 text-[10px] font-mono tracking-widest">🏠 MIS SALAS</p>
                  <button @click="loadMyRooms" class="text-[9px] font-mono text-white/40 hover:text-white">
                    🔄 refrescar
                  </button>
                </div>

                <div v-if="myRoomsLoading" class="text-white/30 text-xs font-mono text-center py-6">
                  Cargando...
                </div>
                <div v-else-if="!myRooms.length"
                  class="bg-black/20 border border-dashed border-white/10 rounded-lg p-6 text-center">
                  <p class="text-white/40 text-xs font-mono">No estás en ninguna sala.</p>
                  <p class="text-white/30 text-[10px] font-mono mt-1">Crea una arriba o únete con un código.</p>
                </div>
                <div v-else class="grid grid-cols-1 gap-2">
                  <button v-for="r in myRooms" :key="r.code"
                    @click="currentRoom = r"
                    class="text-left bg-black/30 hover:bg-black/50 border border-white/10 hover:border-yellow-500/40 rounded-xl p-3 transition group">
                    <div class="flex items-center gap-3">
                      <div class="text-2xl">🏠</div>
                      <div class="flex-1 min-w-0">
                        <p class="text-white font-mono font-bold text-sm truncate">
                          {{ r.name || 'Sala sin nombre' }}
                          <span v-if="r.owner_user_id === myUserId"
                            class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-yellow-900/40 text-yellow-300 ml-1">OWNER</span>
                        </p>
                        <div class="flex items-center gap-2 text-[10px] font-mono mt-0.5">
                          <code class="text-yellow-300/80 tracking-widest">{{ r.code }}</code>
                          <span class="text-white/40">·</span>
                          <span class="text-white/50">👥 {{ r.members.length }}/8</span>
                        </div>
                      </div>
                      <span class="text-white/30 group-hover:text-yellow-300 text-lg">→</span>
                    </div>
                  </button>
                </div>
              </div>
            </div>

            <!-- VISTA DETALLE: cuando currentRoom set -->
            <div v-else class="bg-gradient-to-br from-yellow-900/10 via-black/30 to-purple-900/10 border-2 border-yellow-500/50 rounded-xl p-4">
              <!-- Header con back + acciones -->
              <div class="flex items-center gap-2 mb-3">
                <button @click="onBackToList"
                  class="text-[11px] font-mono px-2 py-1 border border-white/15 text-white/70 hover:text-white hover:border-white/40 rounded">
                  ← Salas
                </button>
                <div class="flex-1 min-w-0">
                  <p class="text-yellow-300 font-mono font-bold text-sm truncate">{{ currentRoom.name || 'Sala sin nombre' }}</p>
                  <code class="text-white/60 font-mono text-base tracking-widest">{{ currentRoom.code }}</code>
                </div>
                <button @click="copyRoomLink" class="text-[10px] font-mono px-2 py-1 border border-white/15 text-white/60 hover:text-white rounded shrink-0">
                  {{ roomCopied ? '✓' : '📋' }} Link
                </button>
              </div>

              <!-- Acciones destructivas -->
              <div class="flex gap-2 mb-3">
                <button v-if="!isRoomOwner" @click="onLeaveCurrent" :disabled="leavingRoom"
                  class="flex-1 text-[10px] font-mono px-2 py-1.5 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded disabled:opacity-30">
                  {{ leavingRoom ? '...' : '🚪 Salir de la sala' }}
                </button>
                <button v-if="isRoomOwner" @click="onDeleteCurrent" :disabled="deletingRoom"
                  class="flex-1 text-[10px] font-mono px-2 py-1.5 border border-red-500/50 text-red-300 hover:bg-red-900/30 rounded disabled:opacity-30">
                  {{ deletingRoom ? '...' : '⚠ Borrar sala (owner)' }}
                </button>
              </div>

              <p class="text-white/40 text-[10px] font-mono mb-2">👥 MIEMBROS ({{ currentRoom.members.length }}/8)</p>
              <div class="grid grid-cols-2 gap-1.5">
                <div v-for="m in currentRoom.members" :key="m.riot_id"
                  class="flex items-center bg-black/30 border border-white/10 rounded px-2 py-1.5 gap-1.5"
                  :class="{ 'border-yellow-500/50': auth?.user.value?.riot_id === m.riot_id }">
                  <!-- Avatar Discord si el miembro tiene cuenta linkeada al riot_id;
                       si no, fallback a inicial. Backend desde 2026-06-18 enriquece
                       get_room_members con LEFT JOIN users. -->
                  <Avatar :discord-id="m.discord_id" :avatar="m.avatar"
                    :username="m.username || m.riot_id" size="xs" />
                  <span class="text-white text-[11px] font-mono truncate">{{ m.username || m.riot_id }}</span>
                  <span v-if="auth?.user.value?.riot_id === m.riot_id"
                    class="text-[8px] font-mono ml-auto text-yellow-300/70">tú</span>
                </div>
              </div>
              <p v-if="!currentRoom.members.length" class="text-white/30 text-xs font-mono text-center py-4 italic">
                Sin miembros aún. Comparte el código.
              </p>

              <!-- Pool de la sala (room bets) -->
              <div class="mt-4 pt-3 border-t border-white/10">
                <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">💰 POOLS · ROOM BETS</p>
                <p class="text-white/30 text-[9px] font-mono mb-2">
                  Cada miembro stakea X TC. Tras start, todos juegan 1 ranked solo. Winners se reparten el pot de los losers. Si todos pierden, el de menor tumor en partidas compartidas cobra 10% del de mayor tumor.
                </p>

                <!-- Crear pool (solo owner) -->
                <div v-if="isRoomOwner" class="bg-black/40 border border-white/10 rounded-lg p-2 mb-3">
                  <div class="flex gap-2 items-center">
                    <input type="number" v-model.number="newPoolStake" :min="10" placeholder="Stake TC"
                      class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none" />
                    <select v-model.number="newPoolHours"
                      class="bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none">
                      <option :value="6">6h</option>
                      <option :value="12">12h</option>
                      <option :value="24">24h</option>
                      <option :value="48">48h</option>
                    </select>
                    <button @click="onCreateRoomBet" :disabled="!newPoolStake || newPoolStake <= 0"
                      class="text-[10px] font-mono px-2.5 py-1 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 text-black font-bold rounded">
                      + Pool
                    </button>
                  </div>
                  <p v-if="poolError" class="text-red-400 text-[10px] font-mono mt-1">{{ poolError }}</p>
                </div>

                <!-- Lista de pools -->
                <div v-if="roomBetsLoading" class="text-white/30 text-[11px] font-mono text-center py-2">
                  Cargando pools...
                </div>
                <div v-else-if="!roomBets.length" class="text-white/30 text-[11px] font-mono text-center py-2 italic">
                  Aún no hay pools. {{ isRoomOwner ? 'Crea uno arriba.' : 'Espera al owner.' }}
                </div>
                <div v-else class="space-y-2">
                  <div v-for="rb in roomBets" :key="rb.id"
                    class="bg-black/30 border border-white/10 rounded-lg px-2 py-2">
                    <div class="flex items-center gap-2 text-[11px] font-mono mb-1">
                      <span class="text-yellow-300 font-bold">{{ rb.stake }} TC</span>
                      <span class="text-white/30">·</span>
                      <span class="text-white/50">{{ (rb.participants || []).length }} miembros</span>
                      <span class="ml-auto text-[9px] uppercase font-bold px-1.5 py-0.5 rounded"
                        :class="rb.status === 'collecting' ? 'bg-cyan-900/40 text-cyan-300'
                              : rb.status === 'active' ? 'bg-yellow-900/40 text-yellow-300'
                              : rb.status === 'resolved' ? 'bg-green-900/40 text-green-300'
                              : 'bg-white/10 text-white/40'">
                        {{ rb.status }}
                      </span>
                    </div>

                    <!-- Lista de participantes -->
                    <div v-if="rb.participants && rb.participants.length" class="space-y-0.5 mb-1">
                      <div v-for="p in rb.participants" :key="p.user_id"
                        class="flex items-center gap-1 text-[10px] font-mono">
                        <span :class="p.user_id === myUserId ? 'text-yellow-300 font-bold' : 'text-white/60'">
                          {{ p.username || '?' }}
                        </span>
                        <span v-if="p.match_id" class="text-white/30">·</span>
                        <span v-if="p.won === 1" class="text-green-400">✓ win</span>
                        <span v-else-if="p.won === 0" class="text-red-400">✗ loss</span>
                        <span v-else-if="p.match_id" class="text-cyan-300">📊 {{ p.tumor_score?.toFixed(0) }}</span>
                        <span v-if="rb.status === 'resolved' && p.payout > 0" class="ml-auto text-yellow-300">
                          +{{ p.payout }} TC
                        </span>
                      </div>
                    </div>

                    <!-- Acciones según status + role -->
                    <div class="flex gap-1.5 mt-1">
                      <button v-if="rb.status === 'collecting' && !isParticipant(rb)" @click="onJoinRoomBet(rb)"
                        class="text-[10px] font-mono px-2 py-0.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                        Unirse · {{ rb.stake }} TC
                      </button>
                      <button v-if="rb.status === 'collecting' && rb.creator_user_id === myUserId" @click="onStartRoomBet(rb)"
                        class="text-[10px] font-mono px-2 py-0.5 bg-green-700 hover:bg-green-600 text-white rounded">
                        ▶ Start
                      </button>
                      <button v-if="rb.status === 'collecting' && rb.creator_user_id === myUserId" @click="onCancelRoomBet(rb)"
                        class="text-[10px] font-mono px-2 py-0.5 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
                        Cancelar
                      </button>
                      <span v-if="rb.status === 'active'" class="text-[10px] font-mono text-white/40 italic">
                        Jugad ranked solo. Polling automático.
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Bravery de la sala -->
              <div class="mt-4 pt-3 border-t border-white/10">
                <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">🎲 BRAVERY · SALA</p>
                <BraveryPanel
                  :room-code="currentRoom.code"
                  :room-bravery-active="!!currentRoom.bravery_active"
                  :is-room-owner="isRoomOwner"
                  @toggle-room-bravery="onToggleRoomBravery" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { ROLE_LABEL } from '../composables/overviewConstants'
import BraveryPanel from './BraveryPanel.vue'
import Avatar from './Avatar.vue'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'

const { confirm } = useConfirm()
const { toast } = useToast()

const props = defineProps<{ show: boolean; initialTab?: string }>()
const emit = defineEmits<{ close: []; refresh: [] }>()

const auth = inject<any>('auth')
const { t } = useI18n()

type TabKey = 'hot' | 'leaderboards' | 'clusters' | 'challenges' | 'bravery' | 'friends' | 'rooms'
const tabs = computed<{ key: TabKey; label: string }[]>(() => [
  { key: 'hot', label: `🔥 ${t('social.hot_bets')}` },
  { key: 'leaderboards', label: `🏆 ${t('social.leaderboards')}` },
  { key: 'clusters', label: `🧬 ${t('social.clusters')}` },
  { key: 'challenges', label: `⚔ ${t('social.challenges')}` },
  { key: 'bravery', label: `🎲 Bravery` },
  { key: 'friends', label: `👥 ${t('social.friends')}` },
  { key: 'rooms', label: `🏠 ${t('social.rooms')}` },
])
const leaderboardKinds = computed(() => [
  { key: 'currency' as const, label: t('social.lb_currency') },
  { key: 'bets' as const, label: t('social.lb_bets') },
  { key: 'accuracy' as const, label: t('social.lb_accuracy') },
])

const active = ref<TabKey>('hot')
const clusters = ref<any[]>([])
const clustersLoading = ref(false)

// 1v1 Challenges state
const myChallenges = ref<any[]>([])
const openChallenges = ref<any[]>([])
const challengesLoading = ref(false)
const challengeError = ref('')
const newChallengeStat = ref<'kills'|'deaths'|'assists'|'kda'|'cs'|'gold'|'damage'|'tumor_score'>('kda')
const newChallengeAmount = ref(50)
const newChallengeFormat = ref<'single'|'bo3'|'tumor_race'|'streak'>('tumor_race')
const newChallengeRival = ref<number | null>(null)

// Metadata visual de cada formato (orden = orden de presentación)
const CHALLENGE_FORMATS = [
  {
    key: 'tumor_race',
    emoji: '⚡',
    name: 'Tumor Race',
    short: 'Race',
    desc: 'Cada uno juega su próxima ranked. Menor tumor score gana.',
    duration: '~40 min',
    color: '#22d3ee',  // cyan-400
  },
  {
    key: 'streak',
    emoji: '🔥',
    name: 'Win Streak',
    short: 'Streak',
    desc: 'Primero en lograr 2 wins seguidas gana. Tracking automático.',
    duration: '~1-3h',
    color: '#f97316',  // orange-500
  },
  {
    key: 'bo3',
    emoji: '⚔',
    name: 'Best of 3',
    short: 'BO3',
    desc: 'Primero en ganar 2 partidas ranked. Tiebreaker por tumor.',
    duration: '~3-6h',
    color: '#a855f7',  // purple-500
  },
  {
    key: 'single',
    emoji: '🎯',
    name: 'Stat Duel',
    short: '1x',
    desc: 'Cada uno submitea 1 partida manualmente. Compara la stat elegida.',
    duration: 'manual',
    color: '#facc15',  // yellow-400
  },
] as const

function formatMeta(key: string) {
  return CHALLENGE_FORMATS.find(f => f.key === key) || CHALLENGE_FORMATS[0]
}

function humanizeTimeUntil(iso: string | null | undefined): string {
  if (!iso) return '?'
  const ms = new Date(iso).getTime() - Date.now()
  if (ms <= 0) return 'expirado'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`
  if (h >= 1) return `${h}h ${m}m`
  return `${m}m`
}

const submittingMatchFor = ref('')   // share_code currently submitting
const matchIdInput = ref('')
const openBets = ref<any[]>([])
const lbKind = ref<'currency' | 'bets' | 'accuracy'>('currency')
const leaderboard = ref<any[]>([])
const friends = ref<any[]>([])
const friendSearchInput = ref('')
const addingFriend = ref(false)
const friendError = ref('')
const newRoomName = ref('')
const joinCodeInput = ref('')
const currentRoom = ref<any>(null)
const roomCopied = ref(false)
const myRooms = ref<any[]>([])
const myRoomsLoading = ref(false)
const leavingRoom = ref(false)
const deletingRoom = ref(false)
const LAST_ROOM_KEY = 'zuruweb-last-room-code'

// Room bets (item #4 UI)
const roomBets = ref<any[]>([])
const roomBetsLoading = ref(false)
const newPoolStake = ref(50)
const newPoolHours = ref(24)
const poolError = ref('')

const isRoomOwner = computed(() => {
  return !!currentRoom.value && currentRoom.value.owner_user_id === myUserId.value
})
function isParticipant(rb: any) {
  return (rb.participants || []).some((p: any) => p.user_id === myUserId.value)
}

async function loadRoomBets() {
  if (!currentRoom.value?.code) return
  roomBetsLoading.value = true
  try {
    roomBets.value = await auth.fetchRoomBets(currentRoom.value.code)
  } catch {
    roomBets.value = []
  } finally {
    roomBetsLoading.value = false
  }
}

watch(() => currentRoom.value?.code, (code) => {
  if (code) loadRoomBets()
  else roomBets.value = []
})

async function onCreateRoomBet() {
  poolError.value = ''
  if (!currentRoom.value || !newPoolStake.value || newPoolStake.value <= 0) return
  try {
    await auth.createRoomBet(currentRoom.value.code, newPoolStake.value, newPoolHours.value)
    await loadRoomBets()
  } catch (e: any) {
    poolError.value = e.message || 'Error'
  }
}

async function onJoinRoomBet(rb: any) {
  poolError.value = ''
  try {
    await auth.joinRoomBet(currentRoom.value.code, rb.id)
    await loadRoomBets()
  } catch (e: any) {
    poolError.value = e.message || 'Error'
  }
}

async function onStartRoomBet(rb: any) {
  const ok = await confirm({
    title: 'Iniciar pool',
    message: `Empieza con ${rb.participants?.length || 0} miembros. Tras esto cada uno juega 1 ranked solo.`,
    confirmText: '▶ Start',
  })
  if (!ok) return
  try {
    await auth.startRoomBet(currentRoom.value.code, rb.id)
    await loadRoomBets()
  } catch (e: any) {
    poolError.value = e.message || 'Error'
  }
}

async function onCancelRoomBet(rb: any) {
  const ok = await confirm({
    title: 'Cancelar pool',
    message: `Refund de ${rb.stake} TC a cada participante.`,
    confirmText: 'Cancelar pool',
    cancelText: 'Volver',
    variant: 'warning',
  })
  if (!ok) return
  try {
    await auth.cancelRoomBet(currentRoom.value.code, rb.id)
    await loadRoomBets()
  } catch (e: any) {
    poolError.value = e.message || 'Error'
  }
}

watch(() => props.show, async v => {
  if (v) {
    if (props.initialTab) active.value = props.initialTab as TabKey
    await loadActive()
  }
})

watch(active, () => loadActive())

async function loadActive() {
  if (active.value === 'hot') openBets.value = await auth.fetchOpenBets()
  if (active.value === 'leaderboards') await loadLeaderboard()
  if (active.value === 'clusters') await loadClusters()
  if (active.value === 'challenges') await loadChallenges()
  if (active.value === 'friends') friends.value = await auth.fetchFriends()
  if (active.value === 'rooms') {
    await loadMyRooms()
    // Re-hidratar sala persistida si sigue siendo mía
    const last = localStorage.getItem(LAST_ROOM_KEY)
    if (last && !currentRoom.value) {
      const found = myRooms.value.find((r: any) => r.code === last)
      if (found) currentRoom.value = found
      else localStorage.removeItem(LAST_ROOM_KEY)
    }
  }
}

async function loadChallenges() {
  challengesLoading.value = true
  try {
    const [mine, open] = await Promise.all([
      auth.fetchMyChallenges(),
      auth.fetchOpenChallenges(),
    ])
    myChallenges.value = mine
    openChallenges.value = open
  } finally {
    challengesLoading.value = false
  }
}

async function onCreateChallenge() {
  challengeError.value = ''
  try {
    await auth.createChallenge({
      statType: newChallengeStat.value,
      amount: newChallengeAmount.value,
      format: newChallengeFormat.value,
      challengedUserId: newChallengeRival.value ?? undefined,
    })
    newChallengeRival.value = null
    await loadChallenges()
  } catch (e: any) {
    challengeError.value = e.message || 'Error'
  }
}

async function onAcceptChallenge(c: any) {
  challengeError.value = ''
  try {
    await auth.acceptChallenge(c.share_code)
    await loadChallenges()
  } catch (e: any) {
    challengeError.value = e.message || 'Error'
  }
}

async function onCancelChallenge(c: any) {
  const ok = await confirm({
    title: 'Cancelar challenge',
    message: `${c.share_code} · refund ${c.amount} TC.`,
    confirmText: 'Cancelar',
    cancelText: 'Volver',
    variant: 'warning',
  })
  if (!ok) return
  try {
    await auth.cancelChallenge(c.share_code)
    await loadChallenges()
  } catch (e: any) {
    challengeError.value = e.message || 'Error'
  }
}

async function onSubmitMatch(c: any) {
  if (!matchIdInput.value.trim()) return
  submittingMatchFor.value = c.share_code
  challengeError.value = ''
  try {
    await auth.submitChallengeMatch(c.share_code, matchIdInput.value.trim())
    matchIdInput.value = ''
    await loadChallenges()
  } catch (e: any) {
    challengeError.value = e.message || 'Error'
  } finally {
    submittingMatchFor.value = ''
  }
}

const myUserId = computed(() => auth?.user.value?.id)
function challengeIamIn(c: any) {
  return c.challenger_user_id === myUserId.value || c.challenged_user_id === myUserId.value
}
function challengeNeedsSubmit(c: any) {
  if (c.status !== 'accepted' || !challengeIamIn(c)) return false
  if (c.challenger_user_id === myUserId.value && !c.challenger_match_id) return true
  if (c.challenged_user_id === myUserId.value && !c.challenged_match_id) return true
  return false
}

async function loadClusters() {
  clustersLoading.value = true
  try {
    const data = await auth.fetchClusters(4)
    clusters.value = data.clusters || []
  } catch {
    clusters.value = []
  } finally {
    clustersLoading.value = false
  }
}

async function loadLeaderboard() {
  leaderboard.value = await auth.fetchLeaderboard(lbKind.value)
}

async function onAccept(b: any) {
  try {
    await auth.acceptBet(b.share_code)
    await loadActive()
    emit('refresh')
  } catch (e: any) {
    toast.error(e.message || 'Error aceptando la apuesta')
  }
}

async function onAddFriend() {
  if (!friendSearchInput.value.trim()) return
  addingFriend.value = true
  friendError.value = ''
  try {
    await auth.addFriend(friendSearchInput.value.trim())
    friendSearchInput.value = ''
    friends.value = await auth.fetchFriends()
  } catch (e: any) {
    friendError.value = e.message || 'Error'
  } finally {
    addingFriend.value = false
  }
}

async function onAcceptFriend(id: number) {
  await auth.acceptFriend(id)
  friends.value = await auth.fetchFriends()
}

async function onRejectFriend(id: number) {
  await auth.rejectFriend(id)
  friends.value = await auth.fetchFriends()
}

async function loadMyRooms() {
  myRoomsLoading.value = true
  try {
    myRooms.value = await auth.fetchMyRooms()
  } finally {
    myRoomsLoading.value = false
  }
}

async function onCreateRoom() {
  try {
    const r = await auth.createRoom(newRoomName.value)
    currentRoom.value = r
    newRoomName.value = ''
    localStorage.setItem(LAST_ROOM_KEY, r.code)
    await loadMyRooms()
  } catch (e: any) {
    toast.error(e.message || 'Error creando la sala')
  }
}

async function onJoinRoom() {
  const code = joinCodeInput.value.trim().toUpperCase()
  if (!code) return
  try {
    const r = await auth.joinRoom(code)
    currentRoom.value = r
    joinCodeInput.value = ''
    localStorage.setItem(LAST_ROOM_KEY, r.code)
    await loadMyRooms()
  } catch (e: any) {
    toast.error(e.message || 'Error uniéndose a la sala')
  }
}

async function onLeaveCurrent() {
  if (!currentRoom.value) return
  const ok = await confirm({
    title: 'Salir de la sala',
    message: `¿Salir de "${currentRoom.value.name || currentRoom.value.code}"?`,
    confirmText: '🚪 Salir',
    variant: 'warning',
  })
  if (!ok) return
  leavingRoom.value = true
  try {
    await auth.leaveRoom(currentRoom.value.code)
    localStorage.removeItem(LAST_ROOM_KEY)
    currentRoom.value = null
    await loadMyRooms()
  } finally {
    leavingRoom.value = false
  }
}

async function onDeleteCurrent() {
  if (!currentRoom.value) return
  const ok = await confirm({
    title: '⚠ Borrar sala',
    message: `Vas a borrar "${currentRoom.value.name || currentRoom.value.code}" para todos los miembros. Esta acción no se puede deshacer.`,
    confirmText: 'Borrar definitivamente',
    cancelText: 'Volver',
    variant: 'danger',
  })
  if (!ok) return
  deletingRoom.value = true
  try {
    const ok = await auth.deleteRoom(currentRoom.value.code)
    if (!ok) {
      toast.error('No se pudo borrar la sala')
      return
    }
    localStorage.removeItem(LAST_ROOM_KEY)
    currentRoom.value = null
    await loadMyRooms()
  } finally {
    deletingRoom.value = false
  }
}

function onBackToList() {
  localStorage.removeItem(LAST_ROOM_KEY)
  currentRoom.value = null
}

async function onToggleRoomBravery() {
  if (!currentRoom.value) return
  const updated = await auth.toggleRoomBravery(currentRoom.value.code)
  if (updated) currentRoom.value = updated
}

async function copyRoomLink() {
  if (!currentRoom.value) return
  const url = `${window.location.origin}${window.location.pathname}#/room/${currentRoom.value.code}`
  try {
    await navigator.clipboard.writeText(url)
    roomCopied.value = true
    setTimeout(() => { roomCopied.value = false }, 2000)
  } catch {}
}
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
