import {defineStore} from "pinia";
import {secureFetch} from "@/services/fetch";
import useMessageStore from "@/store/messages";

export const useTableStore = defineStore("tables", {
  state: () => ({
    tables: {},
  }),
  actions: {
    clear(tableModel) {
      console.log('clear', tableModel)
      if (this.tables[tableModel] !== undefined) {
        this.tables[tableModel].items = [];
        this.tables[tableModel].structure = [];
        this.tables[tableModel] = undefined;
      }
    },
    async reloadTableData(tableModel) {
      const messageStore = useMessageStore();
      if (this.tables[tableModel] === undefined) {
        await this.loadTableData(tableModel)
        return
      }
      // load this table data only
      // this.tables[tableModel].items = [];
    },
    async loadTableData(tableModel, force = false, is_live = false) {
      const messageStore = useMessageStore();
      if (this.tables[tableModel] === undefined || force === true) {
        this.tables[tableModel] = {};
      } else {
        return
      }

      try {
        const structure = await secureFetch(`/api/structure/${tableModel}`)
        const structure_data = await structure.json();
        this.tables[tableModel].structure = structure_data;
        console.log('structure_data', structure_data)

        for (const field of structure_data) {
          if (field.element !== undefined) {
            if (field.element.type === 'alias') {
              await this.loadTableData(field.element.table)
            }
          }
        }

        let url = is_live ? `/api/live/${tableModel}` : `/api/${tableModel}/`
        const data = await secureFetch(url)
        const data_data = await data.json();
        this.tables[tableModel].items = data_data;
      } catch (e) {
        console.warn(e)
        messageStore.addMessage({type: "error", text: `Ошибка загрузки структуры таблицы ${tableModel}.`})
      }
    },

    async saveItem(table, data) {
      console.log('saveItem', table, data)
      const messageStore = useMessageStore();
      const method = data.id ? 'PUT' : 'POST'
      const url = `/api/${table}/${data.id || ''}`
      // only send fields that are in the structure not readonly
      const send_data = {}
      for (const field of this.tables[table].structure) {
        if (field.readonly !== true && data[field.name] !== undefined && data[field.name] !== null) {
          send_data[field.name] = data[field.name]
        }
      }
      try {
        const result = await secureFetch(url, {
          method,
          headers: {'Content-Type': 'application/json'},
          body: send_data,
        }).catch(() => {
          return false
        })
        if (!result) return result
        await this.loadTableData(table)
        messageStore.addMessage({
          type: "info",
          text: data.id ? `Запись ${data.id} обновлена ${table}.` : `Запись добавлена в ${table}.`
        })
        return true
      } catch (e) {
        return false
      }
    },

    async deleteItem(table, id) {
      const messageStore = useMessageStore();
      try {
        await secureFetch(`/api/${table}/${id}`, {
          method: 'DELETE',
        })
        await this.loadTableData(table)
        messageStore.addMessage({type: "info", text: `Запись ${id} удалена из ${table}.`})
      } catch (e) {
        console.warn(e)
        messageStore.addMessage({type: "error", text: `Ошибка удаления записи ${id} из ${table}.`})
      }
    },
  }
});

export default useTableStore;
