<template>
  <!-- 404 page -->
  <v-container>
    <v-row>
      <v-col>
        <h1>404</h1>
        <p>Page not found</p>
        <v-btn @click="goHome">Home</v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
export default {
  name: "NotFound",
  methods: {
    goHome() {
      // Используем router.push для правильной навигации в любом режиме
      this.$router.push('/');
    }
  }
};
</script>

<style></style>
