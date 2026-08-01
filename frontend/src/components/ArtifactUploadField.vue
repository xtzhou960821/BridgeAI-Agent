<script setup lang="ts">
import { ref } from 'vue'

import { artifactContentUrl } from '../api'
import type { ArtifactRecord } from '../types'

defineProps<{
  artifact: ArtifactRecord | null
  busy: boolean
  error: string
}>()

const emit = defineEmits<{ select: [file: File] }>()

const fileInput = ref<HTMLInputElement | null>(null)

function chooseFile() {
  fileInput.value?.click()
}

function selectFirst(files: FileList | File[]) {
  const file = files[0]
  if (file) emit('select', file)
}

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('select', file)
  target.value = ''
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer?.files) selectFirst(event.dataTransfer.files)
}

function formatMebibytes(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MiB`
}
</script>

<template>
  <section class="artifact-upload" aria-label="巡检图片">
    <template v-if="artifact">
      <div class="artifact-ready">
        <img :src="artifactContentUrl(artifact.artifact_id)" :alt="`${artifact.original_filename} 预览`" />
        <div class="artifact-summary">
          <p class="artifact-name">{{ artifact.original_filename }}</p>
          <p class="artifact-state">图片已就绪，可创建巡检任务。</p>
          <dl class="artifact-meta">
            <div><dt>大小</dt><dd>{{ formatMebibytes(artifact.size_bytes) }}</dd></div>
            <div><dt>尺寸</dt><dd>{{ artifact.width_px }} × {{ artifact.height_px }} px</dd></div>
            <div><dt>MIME</dt><dd>{{ artifact.mime_type }}</dd></div>
            <div><dt>校验和</dt><dd>{{ artifact.sha256.slice(0, 12) }}…</dd></div>
            <div><dt>状态</dt><dd>{{ artifact.status }}</dd></div>
          </dl>
          <label class="artifact-id">
            <span>Artifact ID</span>
            <input :value="artifact.artifact_id" readonly aria-label="Artifact ID" />
          </label>
        </div>
      </div>
    </template>
    <template v-else>
      <input
        ref="fileInput"
        class="visually-hidden"
        type="file"
        accept=".jpg,.jpeg,.png,image/jpeg,image/png"
        :disabled="busy"
        @change="handleInput"
      />
      <button
        data-upload-dropzone
        class="upload-dropzone"
        type="button"
        :disabled="busy"
        @click="chooseFile"
        @dragover.prevent
        @drop="handleDrop"
      >
        <strong>{{ busy ? '正在校验并保存图片...' : '上传巡检图片' }}</strong>
        <span v-if="!busy">点击选择，或将一张 JPEG / PNG 图片拖放到此处。</span>
      </button>
      <p v-if="error" class="upload-error" role="alert">{{ error }}</p>
    </template>
  </section>
</template>

<style scoped>
.artifact-upload {
  display: grid;
  gap: 10px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  clip-path: inset(50%);
}

.upload-dropzone {
  display: grid;
  min-height: 112px;
  place-content: center;
  gap: 8px;
  border: 1px dashed #92a79a;
  border-radius: 9px;
  padding: 18px;
  color: #244f3c;
  background: rgba(238, 243, 236, 0.64);
  font: inherit;
  text-align: center;
  cursor: pointer;
}

.upload-dropzone strong {
  font-size: 0.96rem;
}

.upload-dropzone span {
  color: #526058;
  font-size: 0.86rem;
}

.upload-dropzone:disabled {
  cursor: wait;
  opacity: 0.78;
}

.upload-dropzone:focus-visible,
.artifact-id input:focus-visible {
  outline: 3px solid rgba(36, 79, 60, 0.3);
  outline-offset: 2px;
}

.upload-error {
  margin: 0;
  color: #8a2f2f;
  font-weight: 700;
}

.artifact-ready {
  display: grid;
  grid-template-columns: minmax(150px, 220px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  border: 1px solid #cbd5cd;
  border-radius: 9px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.68);
}

.artifact-ready img {
  display: block;
  width: 100%;
  max-height: 160px;
  border-radius: 6px;
  object-fit: cover;
}

.artifact-summary {
  min-width: 0;
}

.artifact-name,
.artifact-state {
  margin: 0;
}

.artifact-name {
  color: #17201a;
  font-weight: 700;
}

.artifact-state {
  margin-top: 4px;
  color: #526058;
  font-size: 0.88rem;
}

.artifact-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin: 12px 0;
  color: #526058;
  font-size: 0.82rem;
}

.artifact-meta div {
  display: flex;
  gap: 4px;
}

.artifact-meta dt {
  font-weight: 700;
}

.artifact-meta dd {
  margin: 0;
}

.artifact-id {
  display: grid;
  gap: 5px;
  color: #526058;
  font-size: 0.78rem;
  font-weight: 700;
}

.artifact-id input {
  width: 100%;
  border: 1px solid #d7dfd8;
  border-radius: 6px;
  padding: 7px 8px;
  color: #526058;
  background: #f5f7f4;
  font: inherit;
}

@media (max-width: 560px) {
  .artifact-ready {
    grid-template-columns: 1fr;
  }

  .artifact-ready img {
    max-width: 260px;
  }
}
</style>
