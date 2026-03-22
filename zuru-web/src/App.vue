<script setup lang="ts">
import { ref } from 'vue';
import Navbar from './components/Navbar.vue';
import DiagnosisForm from './components/DiagnosisForm.vue';
import Mental from './components/Mental.vue';
import Tinder from './components/Tinder.vue';

const currentPage = ref('oncologico');
</script>

<template>
  <div class="h-screen flex flex-col">
    <Navbar :current-page="currentPage" @navigate="currentPage = $event" />
    
    <DiagnosisForm v-if="currentPage === 'oncologico'" />
    <Mental v-else-if="currentPage === 'mental'" />
    <Tinder v-else-if="currentPage === 'tinder'" />
  </div>
</template>
