import { useState } from 'react'
import logo from '/logo.png'
import Header  from "./header.jsx"

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  return (
    <>
    <Header />
      <div>
        <a href="/">
          <img src={logo} className="logo" alt="EasyLot logo" />
        </a>
      </div>
    </>
  )
}

export default App
