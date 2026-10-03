// jsdom doesn't implement scrolling; ChatPanel scrolls its thread to the latest message.
Element.prototype.scrollIntoView = () => {}
