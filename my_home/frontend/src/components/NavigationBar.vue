<template>
  <v-app-bar
    fixed
    density="compact"
    elevation="1"
    color="primary"
  >
    <v-app-bar-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-home</v-icon>
      My Home
    </v-app-bar-title>

    <v-spacer></v-spacer>

    <!-- Кнопки навигации -->
    <v-btn
      variant="text"
      prepend-icon="mdi-devices"
      :to="'/'"
      :active="route.path === '/'"
      class="mr-2"
    >
      Устройства
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-lightning-bolt"
      to="/automation"
      :active="route.path === '/automation'"
      class="mr-2"
    >
      Автоматизация
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-lightning-bolt-circle"
      to="/energy"
      :active="route.path === '/energy'"
      class="mr-2"
    >
      Энергия
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-network"
      to="/virtual-devices"
      :active="route.path === '/virtual-devices'"
      class="mr-2"
    >
      Виртуальные устройства
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-link-variant"
      to="/my-home-link"
      :active="route.path === '/my-home-link'"
      class="mr-2"
    >
      MY HOME Link
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-clipboard-pulse-outline"
      to="/diagnostics"
      :active="route.path === '/diagnostics'"
      class="mr-2"
    >
      Диагностика
    </v-btn>

    <!-- Настройки (только значок, прижато вправо) -->
    <v-btn
      icon
      variant="text"
      @click="showConfigDialog = true"
      class="ml-2"
    >
      <v-icon>mdi-cog-box</v-icon>
    </v-btn>
  </v-app-bar>

  <!-- Диалог настроек -->
  <AddonConfigDialog
    v-model="showConfigDialog"
  />
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AddonConfigDialog from './AddonConfigDialog.vue'

const route = useRoute()
const showConfigDialog = ref(false)
</script>

<style scoped>
</style>
