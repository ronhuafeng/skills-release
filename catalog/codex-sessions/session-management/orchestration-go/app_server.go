package sessionmanagement

import (
	"github.com/ronhuafeng/llm-go/codexsdk"
	"github.com/ronhuafeng/llm-go/codexsdk/protocolv2"
)

func nullableValue[T any](value *protocolv2.Nullable[T]) (T, bool) {
	var zero T
	if value == nil || value.Value == nil {
		return zero, false
	}
	return *value.Value, true
}

func newAppServerClient(cwd string, name string, title string) (*codexsdk.Client, error) {
	return newAppServerClientForCommand(cwd, name, title, []string{"codex", "app-server", "--stdio"})
}

func newAppServerClientForCommand(cwd string, name string, title string, command []string) (*codexsdk.Client, error) {
	return newAppServerClientForCommandWithNotifications(cwd, name, title, command, nil)
}

func newAppServerClientForCommandWithNotifications(
	cwd string,
	name string,
	title string,
	command []string,
	handler codexsdk.ServerNotificationHandler,
) (*codexsdk.Client, error) {
	experimental := true
	return codexsdk.New(codexsdk.ClientOptions{
		CWD:                       cwd,
		Command:                   command,
		ServerNotificationHandler: handler,
		Initialize: protocolv2.InitializeParams{
			Capabilities: protocolv2.Value(protocolv2.InitializeCapabilities{ExperimentalAPI: &experimental}),
			ClientInfo: protocolv2.ClientInfo{
				Name: name, Title: protocolv2.Value(title), Version: "1.0.0",
			},
		},
	})
}

func guardedClose(close func() error) func() error {
	closed := false
	return func() error {
		if closed {
			return nil
		}
		closed = true
		return close()
	}
}
