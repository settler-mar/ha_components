<template>
  <div class="automation-manager">
    <v-card>
      <v-card-title>
        <v-tabs v-model="currentTab" bg-color="transparent">
          <v-tab value="instances">
            <v-icon start>mdi-play-circle</v-icon>
            Автоматизации
          </v-tab>
          <v-tab value="modules">
            <v-icon start>mdi-folder</v-icon>
            Модули
          </v-tab>
        </v-tabs>
      </v-card-title>

      <v-card-text>
        <v-window v-model="currentTab">
          <v-window-item value="instances">
            <InstanceManager />
          </v-window-item>
          <v-window-item value="modules">
            <ModuleManager />
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ModuleManager from './ModuleManager.vue'
import InstanceManager from './InstanceManager.vue'

const currentTab = ref('instances')
</script>

<style scoped>
.automation-manager {
  padding: 16px 0;
}
</style>


