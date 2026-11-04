// Preserve operation behavior; only explicit metadata enters aggregate telemetry.
export async function observeFeatureOperation(report, component, operation, run) {
  const emit = event => { try { report(event); } catch { /* Reporting is best effort. */ } };
  try {
    const result = await run();
    emit({ type: 'internal_operation', component, operation, status: 'success', error_kind: 'none' });
    return result;
  } catch (error) {
    emit({ type: 'internal_operation', component, operation, status: 'error',
      error_kind: typeof error?.code === 'string' ? error.code : 'internal' });
    throw error;
  }
}
