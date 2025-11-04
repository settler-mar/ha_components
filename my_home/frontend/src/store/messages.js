import {defineStore} from "pinia";
import {v4} from "uuid";

const store = defineStore("messages", {
  state: () => {
    return {
      messages: [],
    };
  },
  actions: {
    addMessage({type, message, text}) {
      // Generate a new message id and add it to the messages array
      const newMessageId = v4();
      message = message || text;
      this.messages.push({
        id: newMessageId,
        message,
        type,
      });

      // Remove the message after 5 seconds
      setTimeout(() => {
        this.removeMessage(newMessageId);
      }, 5000);
    },
    removeMessage(id) {
      this.messages = this.messages.filter((message) => message.id !== id);
    },
    // Helper methods for convenience
    showSuccess(message) {
      this.addMessage({type: 'success', text: message});
    },
    showError(message) {
      this.addMessage({type: 'error', text: message});
    },
    showWarning(message) {
      this.addMessage({type: 'warning', text: message});
    },
    showInfo(message) {
      this.addMessage({type: 'info', text: message});
    },
  },
});

export default store;
