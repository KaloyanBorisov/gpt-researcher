interface GetHostParams {
  purpose?: string;
}

export const getHost = ({ purpose }: GetHostParams = {}): string => {
  if (typeof window !== 'undefined') {
    let { host } = window.location;
    const apiUrlInLocalStorage = localStorage.getItem("GPTR_API_URL");
    
    const urlParams = new URLSearchParams(window.location.search);
    const apiUrlInUrlParams = urlParams.get("GPTR_API_URL");
    
    if (apiUrlInLocalStorage) {
      return apiUrlInLocalStorage;
    } else if (apiUrlInUrlParams) {
      return apiUrlInUrlParams;
    } else if (process.env.NEXT_PUBLIC_GPTR_API_URL) {
      return process.env.NEXT_PUBLIC_GPTR_API_URL;
    } else if (process.env.REACT_APP_GPTR_API_URL) {
      return process.env.REACT_APP_GPTR_API_URL;
    } else if (purpose === 'langgraph-gui') {
      return (host.includes('localhost') || host.includes('127.0.0.1')) ? 'http%3A%2F%2F127.0.0.1%3A8123' : `${window.location.protocol}//${window.location.hostname}:8123`;
    } else {
      const proto = window.location.protocol.startsWith('https') ? 'https:' : 'http:';
      const hostname = window.location.hostname || 'localhost';
      return `${proto}//${hostname}:8000`;
    }
  }
  return '';
};