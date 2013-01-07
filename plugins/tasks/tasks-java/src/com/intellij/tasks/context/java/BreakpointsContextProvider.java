/*
 * Copyright 2000-2009 JetBrains s.r.o.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *  http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

package com.intellij.tasks.context.java;

import com.intellij.debugger.DebuggerManager;
import com.intellij.debugger.ui.breakpoints.BreakpointManager;
import com.intellij.debugger.ui.breakpoints.Breakpoint;
import com.intellij.debugger.impl.DebuggerManagerImpl;
import com.intellij.openapi.util.InvalidDataException;
import com.intellij.openapi.util.WriteExternalException;
import com.intellij.tasks.context.WorkingContextProvider;
import org.jdom.Element;
import org.jetbrains.annotations.NotNull;

import java.util.List;

/**
 * @author Dmitry Avdeev
 */
public class BreakpointsContextProvider extends WorkingContextProvider {

  private final DebuggerManager myDebuggerManager;

  public BreakpointsContextProvider(DebuggerManager debuggerManager) {
    myDebuggerManager = debuggerManager;
  }

  @NotNull
  @Override
  public String getId() {
    return "javaDebugger";
  }

  @NotNull
  @Override
  public String getDescription() {
    return "Debugger breakpoints";
  }

  public void saveContext(Element toElement) throws WriteExternalException {
    myDebuggerManager.writeExternal(toElement);
  }

  public void loadContext(Element fromElement) throws InvalidDataException {
    myDebuggerManager.readExternal(fromElement);
  }

  public void clearContext() {
    BreakpointManager breakpointManager = ((DebuggerManagerImpl)myDebuggerManager).getBreakpointManager();
    List<Breakpoint> breakpoints = breakpointManager.getBreakpoints();
    for (Breakpoint breakpoint : breakpoints) {
      breakpointManager.removeBreakpoint(breakpoint);
    }
  }
}
