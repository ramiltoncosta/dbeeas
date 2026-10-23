import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
// Fontes servidas pelo próprio site (sem depender do Google Fonts)
import '@fontsource-variable/inter'
import '@fontsource-variable/bricolage-grotesque'
import './index.css'
import { ProvedorAuth } from './lib/auth'

const clienteConsultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <BrowserRouter>
        <ProvedorAuth>
          <App />
        </ProvedorAuth>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
