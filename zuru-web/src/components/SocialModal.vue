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
                <img v-if="u.avatar && u.discord_id" :src="`https://cdn.discordapp.com/avatars/${u.discord_id}/${u.avatar}.png?size=32`"
                  class="w-7 h-7 rounded-full" />
                <div v-else class="w-7 h-7 rounded-full bg-[#5865F2] flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {{ u.username?.[0]?.toUpperCase() ?? '?' }}
                </div>
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
            <div v-else class="space-y-3">
              <div v-for="c in clusters" :key="c.id"
                class="bg-black/30 border border-white/10 rounded-xl p-3">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-2xl">{{ c.emoji }}</span>
                  <p class="text-white font-mono font-bold">{{ c.name }}</p>
                  <span class="text-[10px] text-white/40 font-mono ml-auto">{{ $t('social.cluster_size', { n: c.size }) }}</span>
                </div>
                <div class="grid grid-cols-2 gap-2 mb-2 text-[10px] font-mono">
                  <p class="text-white/50">{{ $t('social.cluster_avg_prior') }}: <span class="text-yellow-300">{{ c.centroid.avg_prior }}</span></p>
                  <p class="text-white/50">{{ $t('social.cluster_recent') }}: <span class="text-yellow-300">{{ c.centroid.avg_recent }}</span></p>
                  <p class="text-white/50">{{ $t('social.cluster_winrate') }}: <span class="text-green-400">{{ c.centroid.win_rate }}%</span></p>
                  <p class="text-white/50">{{ $t('social.cluster_tilt') }}: <span class="text-orange-400">{{ c.centroid.tilt_frac }}%</span></p>
                </div>
                <div v-if="c.samples.length" class="space-y-1 mt-2">
                  <p class="text-white/30 text-[9px] font-mono tracking-widest">{{ $t('social.cluster_examples') }}</p>
                  <div v-for="(s, i) in (c.samples as any[])" :key="i"
                    class="flex items-center gap-2 text-[10px] font-mono py-0.5">
                    <span class="text-white/40 w-4">{{ Number(i) + 1 }}.</span>
                    <span class="text-white/60 flex-1 truncate">{{ s.tier }} · {{ s.role || '?' }}</span>
                    <span class="text-yellow-300">{{ s.prior_tumor }}</span>
                    <span class="text-white/40">/</span>
                    <span class="text-green-400">{{ s.win_rate }}%</span>
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

            <!-- Crear challenge -->
            <div class="bg-black/30 border border-white/10 rounded-xl p-3 mb-4">
              <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">{{ $t('social.create') }}</p>
              <!-- Format toggle -->
              <div class="grid grid-cols-4 gap-1 mb-2">
                <button v-for="f in ['single', 'bo3', 'bo5', 'bo10']" :key="f"
                  @click="newChallengeFormat = f as any"
                  :class="newChallengeFormat === f ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50' : 'bg-black/40 text-white/50 border-white/10 hover:text-white/80'"
                  class="text-[10px] font-mono px-2 py-1 rounded border transition">
                  {{ f === 'single' ? '1x' : f.toUpperCase() }}
                </button>
              </div>
              <p class="text-white/30 text-[9px] font-mono mb-2">
                {{ newChallengeFormat === 'single'
                  ? 'Cada uno submitea 1 match manualmente.'
                  : 'Background poller cuenta wins en ranked solo. Tiebreaker: menor tumor score acumulado. 7d max.' }}
              </p>
              <div class="grid grid-cols-2 gap-2 mb-2">
                <select v-model="newChallengeStat"
                  :disabled="newChallengeFormat !== 'single'"
                  class="bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none disabled:opacity-50">
                  <option value="kda">KDA</option>
                  <option value="kills">Kills</option>
                  <option value="deaths">Deaths ({{ $t('social.lower_wins_label') }})</option>
                  <option value="assists">Assists</option>
                  <option value="cs">CS</option>
                  <option value="gold">Gold</option>
                  <option value="damage">Damage</option>
                  <option value="tumor_score">☢ Tumor Score</option>
                </select>
                <input type="number" v-model.number="newChallengeAmount" :min="10"
                  class="bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none"
                  :placeholder="$t('social.stake_placeholder')" />
              </div>
              <button @click="onCreateChallenge" :disabled="!newChallengeAmount || newChallengeAmount <= 0"
                class="w-full bg-yellow-600 hover:bg-yellow-500 disabled:bg-yellow-900/40 disabled:text-white/30 text-black font-mono font-bold text-xs px-3 py-1.5 rounded transition">
                {{ $t('social.launch_challenge') }} · {{ newChallengeFormat.toUpperCase() }} · {{ newChallengeAmount }} TC
              </button>
              <p v-if="challengeError" class="text-red-400 text-[10px] font-mono mt-1.5">{{ challengeError }}</p>
            </div>

            <div v-if="challengesLoading" class="text-white/30 text-sm font-mono text-center py-4">
              {{ $t('common.loading') }}
            </div>

            <!-- Mis challenges -->
            <div v-if="myChallenges.length" class="space-y-1.5 mb-4">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">{{ $t('social.my_challenges') }}</p>
              <div v-for="c in myChallenges" :key="c.id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2">
                <div class="flex items-center gap-2 text-xs font-mono flex-wrap">
                  <code class="text-yellow-300">{{ c.share_code }}</code>
                  <span v-if="c.format && c.format !== 'single'"
                    class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300 border border-purple-500/40">
                    {{ c.format.toUpperCase() }}
                  </span>
                  <span class="text-purple-300 font-bold">{{ c.stat_type }}</span>
                  <span class="text-white/40">·</span>
                  <span class="text-yellow-300">{{ c.amount }} TC</span>
                  <span class="text-white/40 ml-auto text-[10px] uppercase">{{ c.status }}</span>
                </div>
                <p v-if="c.format && c.format !== 'single' && (c.challenger_wins || c.challenged_wins)"
                  class="text-white/60 text-[10px] font-mono mt-0.5">
                  Score: <span class="text-cyan-300">{{ c.challenger_wins }}</span>
                  - <span class="text-pink-300">{{ c.challenged_wins }}</span>
                  · meta {{ c.matches_required }}
                </p>
                <p class="text-white/50 text-[11px] font-mono mt-1">
                  <span :class="c.challenger_user_id === myUserId ? 'text-yellow-300 font-bold' : ''">
                    {{ c.challenger?.username || '?' }}
                  </span>
                  <span class="text-white/30 mx-1">vs</span>
                  <span v-if="c.challenged" :class="c.challenged_user_id === myUserId ? 'text-yellow-300 font-bold' : ''">
                    {{ c.challenged.username }}
                  </span>
                  <span v-else class="text-white/30 italic">{{ $t('social.waiting_rival') }}</span>
                </p>

                <!-- Stats si están -->
                <p v-if="c.challenger_value !== null || c.challenged_value !== null" class="text-white/60 text-[10px] font-mono mt-1">
                  <span class="text-cyan-300">A: {{ c.challenger_value ?? '?' }}</span>
                  ·
                  <span class="text-pink-300">B: {{ c.challenged_value ?? '?' }}</span>
                </p>

                <!-- Resultado -->
                <p v-if="c.status === 'resolved'" class="text-[11px] font-mono mt-1 font-bold"
                  :class="c.winner_user_id === myUserId ? 'text-green-400' : c.winner_user_id ? 'text-red-400' : 'text-white/50'">
                  {{
                    c.winner_user_id === myUserId ? $t('social.challenge_won', { amount: c.amount }) :
                    c.winner_user_id ? $t('social.challenge_lost', { amount: c.amount }) :
                    $t('social.challenge_push')
                  }}
                </p>

                <!-- Submit match -->
                <div v-if="challengeNeedsSubmit(c)" class="flex gap-2 mt-2">
                  <input v-model="matchIdInput" placeholder="EUW1_1234567890"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-[11px] focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onSubmitMatch(c)" :disabled="!matchIdInput.trim() || submittingMatchFor === c.share_code"
                    class="text-[10px] font-mono px-2 py-1 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 text-black font-bold rounded">
                    {{ submittingMatchFor === c.share_code ? '...' : $t('social.submit') }}
                  </button>
                </div>

                <!-- Cancel si abierto y soy el creator -->
                <button v-if="c.status === 'open' && c.challenger_user_id === myUserId"
                  @click="onCancelChallenge(c)"
                  class="text-[10px] font-mono px-2 py-1 mt-2 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
                  {{ $t('common.cancel') }}
                </button>
              </div>
            </div>

            <!-- Open challenges feed -->
            <div v-if="openChallenges.length" class="space-y-1.5">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">{{ $t('social.challenges_open_caption') }}</p>
              <div v-for="c in openChallenges.filter((o: any) => o.challenger_user_id !== myUserId)" :key="c.id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex items-center gap-3">
                <div class="flex-1 min-w-0">
                  <p class="text-xs font-mono">
                    <span class="text-cyan-300">{{ c.challenger?.username || '?' }}</span>
                    · <span class="text-purple-300">{{ c.stat_type }}</span>
                    · <span class="text-yellow-300">{{ c.amount }} TC</span>
                  </p>
                </div>
                <button @click="onAcceptChallenge(c)"
                  class="text-[10px] font-mono px-2 py-1 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                  {{ $t('common.accept') }}
                </button>
              </div>
            </div>

            <div v-if="!myChallenges.length && !openChallenges.length && !challengesLoading"
              class="text-white/30 text-sm font-mono text-center py-4">
              {{ $t('social.no_challenges') }}
            </div>
          </div>

          <!-- FRIENDS -->
          <div v-else-if="active === 'friends'">
            <div class="flex gap-2 mb-4">
              <input v-model="friendSearchInput" placeholder="Riot ID (Nombre#TAG)"
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
                <img v-if="f.other_user?.avatar" :src="`https://cdn.discordapp.com/avatars/${f.other_user.discord_id}/${f.other_user.avatar}.png?size=32`"
                  class="w-7 h-7 rounded-full" />
                <div v-else class="w-7 h-7 rounded-full bg-[#5865F2] flex items-center justify-center text-white text-xs font-bold">
                  {{ f.other_user?.username?.[0]?.toUpperCase() ?? '?' }}
                </div>
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
            <div class="grid grid-cols-2 gap-3 mb-4">
              <div class="bg-black/30 border border-white/10 rounded-xl p-3">
                <p class="text-white/40 text-[10px] font-mono mb-2">CREAR SALA</p>
                <div class="flex gap-2">
                  <input v-model="newRoomName" placeholder="Nombre (opcional)"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onCreateRoom"
                    class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                    Crear
                  </button>
                </div>
              </div>
              <div class="bg-black/30 border border-white/10 rounded-xl p-3">
                <p class="text-white/40 text-[10px] font-mono mb-2">UNIRSE POR CÓDIGO</p>
                <div class="flex gap-2">
                  <input v-model="joinCodeInput" placeholder="ABCD12" maxlength="6"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs uppercase focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onJoinRoom"
                    class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                    Entrar
                  </button>
                </div>
              </div>
            </div>

            <div v-if="currentRoom" class="bg-black/30 border border-yellow-500/40 rounded-xl p-4">
              <div class="flex items-center justify-between mb-3">
                <div>
                  <p class="text-yellow-300 font-mono font-bold">{{ currentRoom.name || 'Sala sin nombre' }}</p>
                  <code class="text-white/60 font-mono text-xl tracking-widest">{{ currentRoom.code }}</code>
                </div>
                <button @click="copyRoomLink" class="text-[10px] font-mono px-2 py-1 border border-white/15 text-white/60 hover:text-white rounded">
                  {{ roomCopied ? '✓ Copiado' : '📋 Link' }}
                </button>
              </div>
              <p class="text-white/40 text-[10px] font-mono mb-2">MIEMBROS ({{ currentRoom.members.length }}/8)</p>
              <div class="space-y-1">
                <div v-for="m in currentRoom.members" :key="m.riot_id"
                  class="flex items-center justify-between bg-black/20 border border-white/5 rounded px-2 py-1">
                  <span class="text-white text-xs font-mono">{{ m.riot_id }}</span>
                  <button v-if="auth?.user.value?.riot_id === m.riot_id" @click="onLeaveRoom(m.riot_id)"
                    class="text-[10px] font-mono text-red-400 hover:text-red-300">salir</button>
                </div>
              </div>
              <p v-if="!currentRoom.members.length" class="text-white/30 text-xs font-mono text-center py-4">
                Sin miembros aún. Invita por código.
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
            </div>
            <p v-else class="text-white/30 text-sm font-mono text-center py-8">
              Crea una sala o únete con un código de 6 chars.
            </p>
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

const props = defineProps<{ show: boolean; initialTab?: string }>()
const emit = defineEmits<{ close: []; refresh: [] }>()

const auth = inject<any>('auth')
const { t } = useI18n()

type TabKey = 'hot' | 'leaderboards' | 'clusters' | 'challenges' | 'friends' | 'rooms'
const tabs = computed<{ key: TabKey; label: string }[]>(() => [
  { key: 'hot', label: `🔥 ${t('social.hot_bets')}` },
  { key: 'leaderboards', label: `🏆 ${t('social.leaderboards')}` },
  { key: 'clusters', label: `🧬 ${t('social.clusters')}` },
  { key: 'challenges', label: `⚔ ${t('social.challenges')}` },
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
const newChallengeFormat = ref<'single'|'bo3'|'bo5'|'bo10'>('single')
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
  if (!confirm(`Iniciar pool con ${rb.participants?.length || 0} miembros? Tras esto cada uno juega 1 ranked solo.`)) return
  try {
    await auth.startRoomBet(currentRoom.value.code, rb.id)
    await loadRoomBets()
  } catch (e: any) {
    poolError.value = e.message || 'Error'
  }
}

async function onCancelRoomBet(rb: any) {
  if (!confirm(`Cancelar pool? Refund ${rb.stake} TC a cada participante.`)) return
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
    })
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
  if (!confirm(`¿Cancelar challenge ${c.share_code}? Refund ${c.amount} TC.`)) return
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
    alert(e.message || 'Error')
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

async function onCreateRoom() {
  try {
    currentRoom.value = await auth.createRoom(newRoomName.value)
    newRoomName.value = ''
  } catch (e: any) {
    alert(e.message || 'Error creando sala')
  }
}

async function onJoinRoom() {
  const code = joinCodeInput.value.trim().toUpperCase()
  if (!code) return
  try {
    currentRoom.value = await auth.joinRoom(code)
    joinCodeInput.value = ''
  } catch (e: any) {
    alert(e.message || 'Error uniéndose')
  }
}

async function onLeaveRoom(riotId: string) {
  if (!currentRoom.value) return
  await auth.leaveRoom(currentRoom.value.code, riotId)
  currentRoom.value = await auth.fetchRoom(currentRoom.value.code)
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
