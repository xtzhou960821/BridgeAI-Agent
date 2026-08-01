import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ArtifactUploadField from './ArtifactUploadField.vue'
import type { ArtifactRecord } from '../types'

const artifact: ArtifactRecord = {
  artifact_id: 'art_001',
  original_filename: 'bridge.jpg',
  sha256: '0123456789abcdef'.repeat(4),
  size_bytes: 1_572_864,
  mime_type: 'image/jpeg',
  width_px: 1920,
  height_px: 1080,
  status: 'ready',
  content_url: '/api/v1/artifacts/art_001/content',
  created_at: '2026-08-02T01:00:00+00:00',
}

describe('ArtifactUploadField', () => {
  it('emits the first file selected through the file input', async () => {
    const wrapper = mount(ArtifactUploadField, {
      props: { artifact: null, busy: false, error: '' },
    })
    const file = new File(['jpeg-bytes'], 'bridge.jpg', { type: 'image/jpeg' })

    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
    await input.trigger('change')

    expect(wrapper.emitted('select')).toEqual([[file]])
  })

  it('allows the same file to be selected again after an upload error', async () => {
    const wrapper = mount(ArtifactUploadField, {
      props: { artifact: null, busy: false, error: '' },
    })
    const file = new File(['jpeg-bytes'], 'bridge.jpg', { type: 'image/jpeg' })
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
    Object.defineProperty(input.element, 'value', {
      configurable: true,
      value: 'C:\\fakepath\\bridge.jpg',
      writable: true,
    })

    await input.trigger('change')
    await wrapper.setProps({ error: '上传失败，请重试。' })

    expect(input.element).toHaveProperty('value', '')

    await input.trigger('change')
    expect(wrapper.emitted('select')).toEqual([[file], [file]])
  })

  it('opens the file input when the upload area is clicked', async () => {
    const wrapper = mount(ArtifactUploadField, {
      props: { artifact: null, busy: false, error: '' },
    })
    const fileInput = wrapper.get('input[type="file"]').element as HTMLInputElement
    const click = vi.spyOn(fileInput, 'click')

    await wrapper.get('[data-upload-dropzone]').trigger('click')

    expect(click).toHaveBeenCalledOnce()
  })

  it('emits the first dropped file', async () => {
    const wrapper = mount(ArtifactUploadField, {
      props: { artifact: null, busy: false, error: '' },
    })
    const first = new File(['jpeg-bytes'], 'bridge.jpg', { type: 'image/jpeg' })
    const second = new File(['png-bytes'], 'bridge.png', { type: 'image/png' })

    await wrapper.get('[data-upload-dropzone]').trigger('drop', {
      dataTransfer: { files: [first, second] },
    })

    expect(wrapper.emitted('select')).toEqual([[first]])
  })

  it('shows busy and upload error states accessibly', () => {
    const busy = mount(ArtifactUploadField, {
      props: { artifact: null, busy: true, error: '' },
    })
    const failed = mount(ArtifactUploadField, {
      props: { artifact: null, busy: false, error: '仅支持 JPEG 或 PNG 图片。' },
    })

    expect(busy.text()).toContain('正在校验并保存图片...')
    expect(failed.get('[role="alert"]').text()).toBe('仅支持 JPEG 或 PNG 图片。')
  })

  it('shows ready preview and metadata without replacement controls', () => {
    const wrapper = mount(ArtifactUploadField, {
      props: { artifact, busy: false, error: '' },
    })

    expect(wrapper.get('img').attributes('src')).toBe(
      'http://127.0.0.1:8000/api/v1/artifacts/art_001/content',
    )
    expect(wrapper.text()).toContain('bridge.jpg')
    expect(wrapper.text()).toContain('1.50 MiB')
    expect(wrapper.text()).toContain('1920 × 1080 px')
    expect(wrapper.text()).toContain('image/jpeg')
    expect(wrapper.text()).toContain('0123456789ab')
    expect(wrapper.text()).toContain('ready')
    expect(wrapper.get('input[readonly]').element).toHaveProperty('value', 'art_001')
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
