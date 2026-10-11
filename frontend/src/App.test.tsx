import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock EventSource
class MockEventSource {
  url: string;
  onmessage: ((event: any) => void) | null = null;
  onerror: (() => void) | null = null;
  
  constructor(url: string) {
    this.url = url;
  }
  
  close() {}
}

describe('App Integration', () => {
  beforeEach(() => {
    global.EventSource = MockEventSource as any;
    global.fetch = vi.fn();
  });

  it('submits form and tracks progress', async () => {
    const mockFetch = global.fetch as any;
    mockFetch.mockResolvedValueOnce({
      json: async () => ({ session_id: 'test-session' })
    });
    
    render(<App />);
    
    const input = screen.getByPlaceholderText(/I want to go from New York/i);
    const btn = screen.getByRole('button', { name: /Plan My Trip/i });
    
    expect(btn).toBeDisabled();
    
    await userEvent.type(input, 'Test request');
    expect(btn).not.toBeDisabled();
    
    await userEvent.click(btn);
    
    expect(mockFetch).toHaveBeenCalledWith('http://localhost:8000/api/plan', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ request: 'Test request' })
    }));
    
    expect(screen.getByText(/Planning.../i)).toBeInTheDocument();
  });
});
