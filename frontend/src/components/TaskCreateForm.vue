<script setup lang="ts">
import { ref } from 'vue'

import type { ArtifactRecord, TaskCreateInput } from '../types'
import ArtifactUploadField from './ArtifactUploadField.vue'

const props = defineProps<{
  busy: boolean
  uploading: boolean
  artifact: ArtifactRecord | null
  uploadError: string
}>()

const emit = defineEmits<{
  upload: [file: File]
  create: [input: TaskCreateInput]
}>()

const title = ref('')
const taskType = ref('bridge_inspection')
const objective = ref('')
const validationError = ref('')

function selectArtifact(file: File) {
  emit('upload', file)
}

function submit() {
  const input: TaskCreateInput = {
    title: title.value.trim(),
    task_type: taskType.value.trim(),
    objective: objective.value.trim(),
    artifact_ids: props.artifact ? [props.artifact.artifact_id] : [],
  }
  if (!input.title || !input.task_type || !input.objective || input.artifact_ids.length === 0) {
    validationError.value = '请填写任务名称、任务类型、目标并完成图片上传。'
    return
  }
  validationError.value = ''
  emit('create', input)
}
</script>

<template>
  <form class="task-form" novalidate @submit.prevent="submit">
    <div class="form-grid">
      <label>
        <span>任务名称</span>
        <input v-model="title" name="title" autocomplete="off" placeholder="例如：桥梁无人机影像质量检查" />
      </label>
      <label>
        <span>任务类型</span>
        <input v-model="taskType" name="task_type" autocomplete="off" />
      </label>
      <label class="form-wide">
        <span>任务目标</span>
        <textarea
          v-model="objective"
          name="objective"
          rows="3"
          placeholder="说明本次巡检需要完成什么"
        />
      </label>
      <div class="form-wide">
        <span class="field-label">巡检图片</span>
        <ArtifactUploadField
          :artifact="artifact"
          :busy="uploading"
          :error="uploadError"
          @select="selectArtifact"
        />
      </div>
    </div>
    <div class="form-actions">
      <p v-if="validationError" class="form-error" role="alert">{{ validationError }}</p>
      <button class="primary-button" type="submit" :disabled="busy || uploading || !artifact">
        {{ busy ? '创建中...' : uploading ? '正在上传图片...' : '创建任务' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.task-form,
.form-grid {
  display: grid;
  gap: 16px;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

label {
  display: grid;
  gap: 8px;
  color: #526058;
  font-size: 0.88rem;
  font-weight: 700;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  color: #526058;
  font-size: 0.88rem;
  font-weight: 700;
}

.form-wide {
  grid-column: 1 / -1;
}

input,
textarea {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #cbd5cd;
  border-radius: 9px;
  padding: 11px 12px;
  color: #17201a;
  background: rgba(255, 255, 255, 0.9);
  font: inherit;
  font-weight: 500;
  resize: vertical;
}

input:focus-visible,
textarea:focus-visible,
button:focus-visible {
  outline: 3px solid rgba(36, 79, 60, 0.3);
  outline-offset: 2px;
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
}

.form-error {
  flex: 1;
  margin: 0;
  color: #8a2f2f;
  font-weight: 700;
}

.primary-button {
  min-height: 42px;
  border: 0;
  border-radius: 8px;
  padding: 0 18px;
  color: #fff;
  background: #244f3c;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.primary-button:disabled {
  color: rgba(255, 255, 255, 0.78);
  background: #6e8276;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-wide {
    grid-column: auto;
  }

  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
