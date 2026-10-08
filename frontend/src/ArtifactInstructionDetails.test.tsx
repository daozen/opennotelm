import { act, render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import ArtifactInstructionDetails from './ArtifactInstructionDetails';
import { applyLanguage } from './i18n';

test('saved instructions remain verbatim plain text when switching interface language', async () => {
  const instruction = '  Explain clearly.\n<script>Keep this as text</script>\nUse examples.  ';
  render(<ArtifactInstructionDetails instruction={instruction} />);
  const details = screen.getByText('生成时的自定义说明').closest('details')!;
  expect(details).not.toHaveAttribute('open');
  expect(details.querySelector('p')!.textContent).toBe(instruction);
  expect(details.querySelector('script')).toBeNull();
  await act(() => applyLanguage('en'));
  expect(screen.getByText('Generation instructions')).toBeInTheDocument();
  expect(details.querySelector('p')!.textContent).toBe(instruction);
});

test('old artifacts with no instructions explain the absence', () => {
  render(<ArtifactInstructionDetails />);
  expect(screen.getByText('生成时未填写自定义说明。')).toBeInTheDocument();
});
