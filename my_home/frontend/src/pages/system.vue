<template>
  <div>
    <!-- Навигационное меню -->
    <v-app-bar density="compact" elevation="1" class="mb-4">
      <v-app-bar-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-cog</v-icon>
        Бэкапы
      </v-app-bar-title>
      
      <v-spacer></v-spacer>
      
      <v-btn
        variant="text"
        prepend-icon="mdi-home"
        to="/"
        class="mr-2"
      >
        Устройства
      </v-btn>
    </v-app-bar>
    
    <!-- Основной контент -->
    <SystemBackupInfo />
  </div>
</template>

<script setup>
import SystemBackupInfo from '@/components/SystemBackupInfo.vue'
</script>

<style scoped>
/* Дополнительные стили для страницы системной информации */
</style>
