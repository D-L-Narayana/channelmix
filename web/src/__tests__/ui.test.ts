import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import Button from '../components/ui/Button.vue'
import Badge from '../components/ui/Badge.vue'
import Dialog from '../components/ui/Dialog.vue'
import Table from '../components/ui/Table.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import Input from '../components/ui/Input.vue'

describe('ui primitives', () => {
  it('Button: variants, loading disables and sets aria-busy', () => {
    const w = mount(Button, { props: { variant: 'primary', loading: true }, slots: { default: 'Go' } })
    expect(w.classes()).toContain('v-primary')
    expect(w.attributes('disabled')).toBeDefined()
    expect(w.attributes('aria-busy')).toBe('true')
    expect(w.text()).toBe('Go')
  })
  it('Badge: tone class', () => {
    expect(mount(Badge, { props: { tone: 'success' }, slots: { default: 'ok' } }).classes()).toContain('success')
  })
  it('Input: wires label, error message and aria-invalid', async () => {
    const w = mount(Input, { props: { label: 'Email', modelValue: '', error: 'Required' } })
    const input = w.find('input')
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(w.find('[role="alert"]').text()).toBe('Required')
    await input.setValue('a@b.co')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['a@b.co'])
  })
  it('Dialog: renders in body with role=dialog and closes on Escape', async () => {
    const w = mount(Dialog, { props: { open: true, title: 'Confirm' }, slots: { default: '<button>x</button>' }, attachTo: document.body })
    await nextTick()
    const dlg = document.body.querySelector('[role="dialog"]')
    expect(dlg).not.toBeNull()
    expect(dlg?.getAttribute('aria-modal')).toBe('true')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(w.emitted('close')).toHaveLength(1)
    w.unmount()
  })
  it('Table: sortable headers expose aria-sort and emit update:sort', async () => {
    const w = mount(Table, {
      props: { columns: [{ key: 'a', label: 'A', sortable: true }, { key: 'b', label: 'B', align: 'right', sortable: true }], rows: [{ a: 'x', b: 1 }], rowKey: (r: { a: string }) => r.a, sort: { key: 'a', dir: 'asc' } },
    })
    const ths = w.findAll('th')
    expect(ths[0].attributes('aria-sort')).toBe('ascending')
    await ths[1].find('button').trigger('click')
    expect(w.emitted('update:sort')?.[0]).toEqual([{ key: 'b', dir: 'desc' }])
  })
  it('Table: loading renders skeleton rows instead of data', () => {
    const w = mount(Table, { props: { columns: [{ key: 'a', label: 'A' }], rows: [], rowKey: () => 1, loading: true, skeletonRows: 3 } })
    expect(w.findAll('tbody tr')).toHaveLength(3)
  })
  it('EmptyState: has a status role, title, body and actions', () => {
    const w = mount(EmptyState, { props: { title: 'Nothing here', body: 'Do X' }, slots: { actions: '<button>Act</button>' } })
    expect(w.attributes('role')).toBe('status')
    expect(w.text()).toContain('Nothing here')
    expect(w.find('button').text()).toBe('Act')
  })
})
