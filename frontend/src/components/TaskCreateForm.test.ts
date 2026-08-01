import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskCreateForm from './TaskCreateForm.vue'
import type { ArtifactRecord } from '../types'

const artifact: ArtifactRecord = {
  artifact_id: 'art_001',
  original_filename: 'bridge.jpg',
  sha256: 'a'.repeat(64),
  size_bytes: 1_572_864,
  mime_type: 'image/jpeg',
  width_px: 1920,
  height_px: 1080,
  status: 'ready',
  content_url: '/api/v1/artifacts/art_001/content',
  created_at: '2026-08-02T01:00:00+00:00',
}

describe('TaskCreateForm', () => {
  it('validates blank input and emits a task payload with the ready artifact', async () => {
    const wrapper = mount(TaskCreateForm, {
      props: { busy: false, uploading: false, artifact: null, uploadError: '' },
    })

    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('请填写任务名称、任务类型、目标并完成图片上传。')
    expect(wrapper.emitted('create')).toBeUndefined()

    await wrapper.get('input[name="title"]').setValue('  桥梁巡检  ')
    await wrapper.get('textarea[name="objective"]').setValue('  检查无人机影像  ')
    await wrapper.setProps({ artifact })
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('create')).toEqual([
      [
        {
          title: '桥梁巡检',
          task_type: 'bridge_inspection',
          objective: '检查无人机影像',
          artifact_ids: ['art_001'],
        },
      ],
    ])
  })

  it('forwards a selected image to the upload handler', async () => {
    const wrapper = mount(TaskCreateForm, {
      props: { busy: false, uploading: false, artifact: null, uploadError: '' },
    })
    const file = new File(['png-bytes'], 'bridge.png', { type: 'image/png' })

    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
    await input.trigger('change')

    expect(wrapper.emitted('upload')).toEqual([[file]])
  })

  it('disables submission while uploading, creating, or awaiting an artifact', () => {
    const wrapper = mount(TaskCreateForm, {
      props: { busy: true, uploading: false, artifact, uploadError: '' },
    })

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('创建中...')

    const pending = mount(TaskCreateForm, {
      props: { busy: false, uploading: true, artifact: null, uploadError: '' },
    })
    expect(pending.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(pending.get('button[type="submit"]').text()).toBe('正在上传图片...')

    const awaitingArtifact = mount(TaskCreateForm, {
      props: { busy: false, uploading: false, artifact: null, uploadError: '' },
    })
    expect(awaitingArtifact.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})
