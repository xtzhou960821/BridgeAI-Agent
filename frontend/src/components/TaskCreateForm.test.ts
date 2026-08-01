import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TaskCreateForm from './TaskCreateForm.vue'

describe('TaskCreateForm', () => {
  it('validates blank input and emits a normalized task payload', async () => {
    const wrapper = mount(TaskCreateForm, { props: { busy: false } })

    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('请填写任务名称、任务类型、目标和至少一个 Artifact ID。')
    expect(wrapper.emitted('create')).toBeUndefined()

    await wrapper.get('input[name="title"]').setValue('  桥梁巡检  ')
    await wrapper.get('textarea[name="objective"]').setValue('  检查无人机影像  ')
    await wrapper.get('textarea[name="artifact_ids"]').setValue(' art_001, art_002\n ')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('create')).toEqual([
      [
        {
          title: '桥梁巡检',
          task_type: 'bridge_inspection',
          objective: '检查无人机影像',
          artifact_ids: ['art_001', 'art_002'],
        },
      ],
    ])
  })

  it('disables submission and reports progress while busy', () => {
    const wrapper = mount(TaskCreateForm, { props: { busy: true } })

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').text()).toBe('创建中...')
  })
})
