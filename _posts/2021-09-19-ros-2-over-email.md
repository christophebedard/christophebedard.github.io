---
layout: post
title: "ROS 2 Over Email: rmw_email, an Actual Working RMW Implementation"
date: 2021-09-19
excerpt: "Ever wanted to use emails to exchange ROS 2 messages? Yes? Well, now you can!"
tags: [ROS, ROS 2, middleware, rmw, email, DDS]
comments: false
---

{% include figure.html
    url="/assets/img/rmw-email/demo_service.png"
    caption="Service request and response using rmw_email. Messages are exchanged as strings using emails."
    alt="service request email from client@rmw-email.com and response reply email from server@rmw-email.com"
    img-style="border: 2px solid #383838;"
%}

{% include tl-dr.html
    content="ROS 2's architecture allows for using almost any middleware, as long as it's done through RMW, the middleware interface. <a href='https://github.com/christophebedard/rmw_email'>rmw_email</a> contains a middleware that sends & receives strings over email and an RMW implementation that allows ROS 2 to use this middleware to exchange messages. While it's certainly not a production-level middleware, it provides interesting insight into the pros and cons of ROS 2's architecture. Abstractions definitely have a cost, but they're also quite powerful: they allow ROS 2 to run over email without needing to modify it at all!"
%}

1. TOC
{:toc}

## Introduction

ROS 2's architecture and underlying middleware are vastly different from ROS 1's, in part because ROS 2 is targeted at real-time distributed applications.
The middleware interface, `rmw`, is an abstraction that allows ROS 2 to support multiple different middleware implementations.
On top of that, there's `rcl`, which provides a common implementation in C to support client libraries for any language.
Finally, there's `rclcpp` and `rclpy`, the C++ and Python client libraries, respectively.
While there definitely are downsides to these abstractions and interfaces, this architecture is very powerful.

In this post, I'll present [rmw_email](https://github.com/christophebedard/rmw_email), which allows ROS 2 to exchange messages using emails.
I'll start by explaining the motivation behind rmw_email.
Then I'll provide an overview and explain how each component works.
After that, I'll show a couple of demos and present the results of performance experiments.
Finally, I'll briefly discuss limitations and possible future work, and then I'll conclude.

## Motivation

The main motivation for rmw_email was my [master's](/about/#education).
I got the high-level idea for this in June of 2020.
At that point, I had been working on and around ROS 2 for about a year.
I had interacted a lot more with the higher levels of the ROS 2 architecture (`rclcpp`, `rcl`) while working on [`ros2_tracing`](https://gitlab.com/ros-tracing/ros2_tracing),
so I wanted to dig deeper into the middleware level and below (`rmw`, DDS/other middleware).

I was also seeing some interesting discussions involving middlewares and the middleware interface.
Developers of real-time applications (e.g., automotive) wanted to expose middleware features that were rather DDS-specific through `rmw`.
This could possibly make the abstraction "leak," thereby breaking it at least slightly.
Of course, it's a tradeoff between maintaining the abstraction itself to keep the benefits vs. making ROS 2 more powerful by allowing users to leverage advanced middleware features and possibly reducing the costs of the abstraction and the general overhead of ROS 2. {% include ref_link.html start="1" end="2" %}

Also, at the time, there weren't many non-DDS `rmw` implementations;
even if they do exist, there are actually currently no non-DDS implementations listed under the [latest ROS 2 distro in REP 2000](https://www.ros.org/reps/rep-2000.html#galactic-geochelone-may-2021-november-2022).
Perhaps adding another one -- as absurd as it may be -- could help diversify the ROS 2 middleware implementations and illustrate how useful the current abstraction can be.
This was even [on the ROS 2 roadmap](https://github.com/ros2/ros2_documentation/pull/964/files#diff-c29e698395f4491092719353da00819ebb5f2c311e3b74e540eb1c6a5af0bcaaR154) at some point.

And, also, why not?
We just *can*!
Sure, DDS is a proven standard to exchange messages, but so is email!
Besides, I don't own a fax machine.

## Overview

rmw_email, the repository/project, consists mainly of two packages: `email`, the middleware, and `rmw_email_cpp`, the RMW implementation.

`email` is a simple middleware with the publisher/subscriber pattern to send and receive string messages on topics.
It also natively supports the service client/server (RPC) pattern.
As its name suggests, emails are used to send messages: the topic or service name is the email subject and the message content is the email body.

`rmw_email_cpp` is an implementation of the ROS 2 middleware interface, `rmw`, using `email`.
It uses an external package that does the hard work to convert messages to YAML.
Then it converts them to YAML strings and passes them on to `email`.
Indeed, `email` knows nothing about all the different ROS 2 messages; it simply handles strings.

## The components of a working(ish) RMW implementation

In the beginning, I had a rough goal: get ROS 2 working *over email*.
Fortunately, in a way, it's a rather straightforward process, since it can be split into a few components.

### Middleware

The middleware should really be usable on its own, so I started by only focusing on that.

At its core, `email` simply sends and receives emails using [`libcurl`](https://curl.se/libcurl/)'s C API.
Emails are sent using the SMTP protocol and received by polling using the IMAP protocol.
Polling is done by first getting the unique identifier (UID {% include ref_link.html start="3" end="3" %}) of the next expected email using the `EXAMINE` IMAP command {% include ref_link.html start="4" end="4" %}.
Then it polls until there's a new email, increments the UID value, and repeats the process.
Polling is done on a dedicated thread, while emails are sent synchronously ([currently](https://github.com/christophebedard/rmw_email/issues/237), at least).

Each email message contains metadata that is included as both custom and standard email headers.
All emails include a source timestamp and the GID (i.e., a unique ID) of the source object (i.e., publisher, service client, or service server).
Additionally, service requests and responses contain a sequence number, and service responses also contain the GID of the service client that made the original request.
This is required so that the service response is matched with the original request and delivered to the corresponding service client.

Also, service responses are email replies to the corresponding service request email!
This is achieved using standard headers: the values of the `In-Reply-To` and `References` headers of the response email are set to the value of the `Message-ID` header of the request email {% include ref_link.html start="5" end="5" %}.
All of this is possible without polluting the email as shown in a normal email client.

Let's illustrate this with the simple server/client example below.

<!-- using Bootstrap might be better, but it interferes with the rest of the style, so just use flex -->
<div style="display: flex; flex-wrap: wrap">
<div style="flex: 50%; padding: 2px">
<!-- receive.email.log -->
{% highlight text %}
Message-ID: <a1.b2@mx.rmw-email.com>
Client-GID: 4074879933
Request-Sequence-Number: 42
Source-Timestamp: 1631797734037229979
In-Reply-To: 
References: 
From: client@rmw-email.com
To: server@rmw-email.com
Cc: 
Bcc: 
Subject: /my_service

this is my request!
{% endhighlight %}
</div>
<div style="flex: 50%; padding: 2px">
<!-- send.email.log -->
{% highlight text %}
Message-ID: <d4.f5@mx.rmw-email.com>
Client-GID: 4074879933
Request-Sequence-Number: 42
Source-Timestamp: 1631797743507593177
In-Reply-To: <a1.b2@mx.rmw-email.com>
References: <a1.b2@mx.rmw-email.com>
From: server@rmw-email.com
To: client@rmw-email.com
Cc: 
Bcc: 
Subject: /my_service

this is a response!
{% endhighlight %}
</div>
</div>

The server will receive the email on the left for the request and the client will receive the email reply on the right for the response.

When a new email is received by the polling thread, it is passed on to email handlers.
All subscriptions, service clients, and service servers register with those handlers.
Handlers use the email's headers and topic/service name to figure out what kind of message it is and which object it belongs to.

Since sending and receiving emails requires an email account, the path to a [configuration file](https://github.com/christophebedard/rmw_email#configuration) with email login credentials and recipients (to/cc/bcc) must be provided through an environment variable.
There is also an intraprocess mode.
If enabled, `email` acts as if it was sending emails to itself, bypassing the very last step of sending/receiving emails.
This means that it still relies on email headers, so it has to fake the `Message-ID` header value, since it is normally added by the email server.

The [`email` design document](https://christophebedard.com/rmw_email/design/email/) contains a lot more information and even contains fancy UML diagrams!
The [API documentation](https://christophebedard.com/rmw_email/api/email/) can also provide more insight.
Along with that, the [`email_examples` package](https://github.com/christophebedard/rmw_email/tree/master/email_examples) contains [many examples](https://github.com/christophebedard/rmw_email#email-examples).

While certainly time-consuming, this part was rather fun to create from scratch.

### Common message representation

Since we have a middleware that strictly deals with strings, we need to be able to convert ROS 2 messages to strings and convert those strings back to messages.

I knew about type support introspection from reading ROS 2 source code and documentation.
It provides metadata about a given message type that allows you to parse the fields of a message given only a type-erased pointer to the message (i.e., `void *`).
Note that it would have been possible to *generate* code that does this for each message type, similar to how a [`to_yaml()` function is generated](https://github.com/ros2/rosidl/blob/36ed120f43daeaab31fd9ba2bf8dfb58db05091d/rosidl_generator_cpp/resource/msg__traits.hpp.em#L131) for each message type.
Also, `rosidl_runtime_py` can [convert YAML strings to messages](https://github.com/ros2/rosidl_runtime_py/blob/63a9c99ad735ef08b9cfda69ba35322b5f8b75f3/rosidl_runtime_py/set_message.py#L28) (e.g., for `ros2 topic pub`), but it’s in Python.

My first idea was to convert the bytes of the messages to [Base64](https://en.wikipedia.org/wiki/Base64) and send that string over email, but that would have been a bit boring.
A while later, after I had a basic working middleware, I saw a [post on ROS Discourse](https://discourse.ros.org/t/ros2-c-based-dynamic-typesupport-example/19079/3) about a [package to convert messages to a YAML representation](https://github.com/osrf/dynamic_message_introspection).
It only supported C messages, though, which was a problem since I needed to support both C and C++ messages.
I looked over the code to see how it worked and then I looked at the [ROS 2 IDL documentation](https://design.ros2.org/articles/idl_interface_definition.html) and [this document](https://docs.ros.org/en/rolling/Concepts/About-ROS-Interfaces.html) to understand what I needed to change to adapt it to C++.
C structures for message arrays make this task simple -- at the expense of being more complex to use -- since they keep track of size and capacity.
C++ containers make it complicated!

For example, how can you [figure out the size of a `std::vector<T>`](https://github.com/christophebedard/dynamic_message_introspection/blob/4afd27793d20731a758eb868459a8b1db6186e41/dynmsg/src/message_reading_cpp.cpp#L519-L520) if you know the size of the contained type, `sizeof(T)`, but *only* have a `void *` to it?
This is the case for unbounded dynamic arrays of a non-built-in type, like an [array of `PointField` in a `PointCloud2` message](https://github.com/ros2/common_interfaces/blob/a3a0dde2ba184b01cdc59a3003728906de3240a9/sensor_msgs/msg/PointCloud2.msg#L19).
The answer is: by ~~Googling it~~ knowing implementation details!
A `std::vector` object simply contains three pointers: begin, end, and end capacity.
Since the elements are stored [contiguously](https://en.cppreference.com/w/cpp/named_req/ContiguousContainer), size is simply [`(end - begin) / sizeof(T)`](https://github.com/christophebedard/dynamic_message_introspection/blob/4afd27793d20731a758eb868459a8b1db6186e41/dynmsg/src/vector_utils.cpp#L49-L59)!
Fun fact: that trick doesn't work with `std::vector<bool>`, because [its implementation is different](https://en.cppreference.com/w/cpp/container/vector_bool), but that's not a problem here.

I forked the package, [added support for C++ messages, made the message<-->YAML conversion symmetrical, and refactored the repository/packages a bit](https://github.com/osrf/dynamic_message_introspection/pull/15).
Below is a simple example of a C++ `std_msgs/Header` message and the corresponding YAML representation.

<div style="display: flex; flex-wrap: wrap">
<div style="flex: 50%; padding: 2px">
{% highlight cpp %}
builtin_interfaces::msg::Time stamp;
stamp.sec = 4;
stamp.nanosec = 20U;
std_msgs::msg::Header msg;
msg.stamp = stamp;
msg.frame_id = "my_frame";
{% endhighlight %}
</div>
<div style="flex: 50%; padding: 2px">
<br>
{% highlight yaml %}
stamp:
  sec: 4
  nanosec: 20
frame_id: my_frame
{% endhighlight %}
</div>
</div>

Even starting from the implementation for C messages, writing the introspection code for C++ messages was a nice challenge.
I’m sure some things could be improved and I might have done some things wrong (although it does work!).
It could nonetheless serve as another example of how to do type support introspection.

### RMW implementation

To tie everything together, we need to implement the `rmw` interface for `email`.

Writing the implementation, `rmw_email_cpp`, was fairly straightforward.
I primarily read the [`rmw` API documentation](https://github.com/ros2/rmw/blob/master/rmw/include/rmw/rmw.h) and looked at other implementations, like [`rmw_cyclonedds_cpp`](https://github.com/ros2/rmw_cyclonedds/tree/master/rmw_cyclonedds_cpp/src) and [`rmw_fastrtps_cpp`](https://github.com/ros2/rmw_fastrtps).
This [summary](https://docs.google.com/presentation/d/1KiRtiMgLCTMV1BeAV_HerHUBfKdC8wjXjRN6-M0LV_U/edit) was also pretty useful to get started!

I knew I would have to modify `email` in order to support the requirements of the `rmw` interface.
However, it wasn't until I started working on the implementation that I figured out what I needed to add.
The main missing feature was wait sets.
With early versions of `email`, users ~~had~~ would have had to manually poll a subscription for new messages.
This is of course not how ROS 2 works; it uses wait sets which allow waiting on different events at the same time in a standard way.
For example, you can add all subscriptions, service clients, and service servers to the wait set and ask it to [wait](https://github.com/ros2/rclcpp/blob/2801553d61c5a30a0327d5cbc8d28bcd74e9703d/rclcpp/include/rclcpp/wait_set_template.hpp#L610-L654).
Once that's done, you can check the wait set to get a list of objects that have a new message, response, or request, and deal with them appropriately.

Some of those features weren't *necessary* for a simple email-based string pub/sub/service "middleware," but adding them definitely improved it and turned it into a sort-of middleware.
Obviously, the `rmw` interface has many other features, like quality of service (for *real* applications) and introspection (e.g., to support `ros2 topic list`).
Those are not currently supported by `rmw_email_cpp`, but PRs are welcome!

This layer is where I saw the downsides of the ROS 2 abstractions.
Many things are duplicated or very similar: APIs, data structures, arguments validation, etc.
Calls often go from `rclcpp` to `rcl` to `rmw` and, finally, to the middleware.
While each layer does have its own responsibilities -- otherwise we wouldn't have all those layers -- a lot of the actual work is done by the middleware.
Furthermore, since DDS has always been the main -- and pretty much only -- middleware standard, parts of the interface, like the [writer GUID field in the request ID struct](https://github.com/ros2/rmw/blob/35fc6ab8fad4db90eb55db9d1ecf50dc1aa3638d/rmw/include/rmw/types.h#L351-L352), are rather DDS-specific.

However, I also saw the clear benefits of these abstractions and interfaces.
I didn't have to write too much code to plug `email` into ROS 2; I only had to implement an interface.
A few bugs aside, after implementing the main `rmw` functions, running ROS 2 over email just... worked!

## Demo

After all of that, it's time for a demo!
First, let's see what our email inbox looks like when running the classic [talker/listener demo](https://github.com/ros2/demos/tree/master/demo_nodes_cpp/src/topics).

<!-- EMAIL_CONFIG_FILE=send.email.yml RMW_IMPLEMENTATION=rmw_email_cpp ros2 run demo_nodes_cpp talker -->
<figure>
<div style="display: flex; flex-wrap: wrap">
<div style="flex: 50%; padding: 2px">
<!-- make the code align vertically with the image -->
<br>
<br>
{% highlight shell %}
$ EMAIL_CONFIG_FILE=talker.email.yml \
  RMW_IMPLEMENTATION=rmw_email_cpp \
  ros2 run demo_nodes_cpp talker
{% endhighlight %}
</div>
<div style="flex: 50%; padding: 2px">
{% include image.html
    url="/assets/img/rmw-email/demo_talker.png"
    alt="'hello world' talker emails from talker@rmw-email.com"
    style="border: 1px solid #383838;"
%}
</div>
</div>
<figcaption style="text-align: center;">Command to run the <code class='highlighter-rouge'>talker</code> node with <code class='highlighter-rouge'>rmw_email_cpp</code> and resulting emails on the <code class='highlighter-rouge'>/chatter</code> topic.</figcaption>
</figure>

Since messages only go in one direction in the above example, let's see a client/server example using the [add_two_ints service demo](https://github.com/ros2/demos/tree/master/demo_nodes_cpp/src/services).

<!-- EMAIL_CONFIG_FILE=send.email.yml RMW_IMPLEMENTATION=rmw_email_cpp ros2 run demo_nodes_cpp add_two_ints_client -->
<!-- EMAIL_CONFIG_FILE=receive.email.yml RMW_IMPLEMENTATION=rmw_email_cpp ros2 run demo_nodes_cpp add_two_ints_server -->
<figure>
<div style="display: flex; flex-wrap: wrap">
<div style="flex: 50%; padding: 2px">
{% highlight shell %}
$ EMAIL_CONFIG_FILE=client.email.yml \
  RMW_IMPLEMENTATION=rmw_email_cpp \
  ros2 run demo_nodes_cpp add_two_ints_client
Result of add_two_ints: 5

$ EMAIL_CONFIG_FILE=server.email.yml \
  RMW_IMPLEMENTATION=rmw_email_cpp \
  ros2 run demo_nodes_cpp add_two_ints_server
Incoming request
a: 2 b: 3
{% endhighlight %}
</div>
<div style="flex: 50%; padding: 2px">
<br>
{% include image.html
    url="/assets/img/rmw-email/demo_service.png"
    alt="service request email from client@rmw-email.com and response reply email from server@rmw-email.com"
    style="border: 1px solid #383838;"
%}
</div>
</div>
<figcaption style="text-align: center;">Commands and emails for the <code class='highlighter-rouge'>/add_two_ints</code> service request and response.</figcaption>
</figure>

As mentioned previously, we can see the reply to the request email in this example.

## Performance

We can use [performance_test](https://gitlab.com/ApexAI/performance_test) to measure pub/sub latencies and compare them to another RMW implementation.
The current default implementation is `rmw_cyclonedds_cpp`, so let's compare to that.

{% include figure.html
    url="/assets/img/rmw-email/perf_comparison_nort.png"
    caption="Latency comparison between <code class='highlighter-rouge'>rmw_email_cpp</code> and <code class='highlighter-rouge'>rmw_cyclonedds_cpp</code>."
    alt="rmw_email_cpp's mean latency is way higher and more jittery compared to rmw_cyclonedds_cpp's"
%}

With a mean latency of around 6 seconds over the one-minute experiment, `rmw_email_cpp` is clearly worse than `rmw_cyclonedds_cpp`.
Approximately 15&thinsp;332 times worse.
Not that we expected anything else, obviously!

The results are different if we run the experiments on a real-time system: PREEMPT_RT-patched Ubuntu Server 20.04.2 (5.4.3-rt1), Intel i7-3770 4-core CPU @ 3.40 GHz (SMT disabled), 8 GB RAM, and SCHED_FIFO policy with the highest priority (99).

{% include figure.html
    url="/assets/img/rmw-email/perf_comparison_rt.png"
    caption="Latency comparison between <code class='highlighter-rouge'>rmw_email_cpp</code> and <code class='highlighter-rouge'>rmw_cyclonedds_cpp</code> on a real-time system."
    alt="rmw_cyclonedds_cpp's mean latency is cut in half, while rmw_email_cpp's mean latency more than doubles"
%}

As expected, the latencies for `rmw_cyclonedds_cpp` are much lower on a real-time system.
However, the latencies for `rmw_email_cpp` get worse!
The data also stops halfway through the experiment because performance_test throws an exception if messages are not received in the order that they are sent.
This assertion could be removed from the performance_test code to compare two complete experiments, but, surely, it's not a good sign when a middleware shuffles messages!

We could pose that most of the time is spent between the two `libcurl` calls to send and receive emails, i.e., server-side.
To explore this hypothesis, we can enable intraprocess mode for `email` and run the experiments again.

{% include figure.html
    url="/assets/img/rmw-email/perf_comparison_intra.png"
    caption="Latency comparison between <code class='highlighter-rouge'>rmw_email_cpp</code> (intraprocess) and <code class='highlighter-rouge'>rmw_cyclonedds_cpp</code>."
    alt="rmw_email_cpp's mean latency in intraprocess mode goes down to 4.41 ms"
%}

The latencies are then much more comparable.
They're now only about 12 times higher, although it would be worse if we did a fair comparison using Cyclone DDS with [iceoryx](https://github.com/eclipse-iceoryx/iceoryx) for shared memory inter-process communications.
`rmw_email_cpp`'s message<-->YAML conversion is without a doubt no match for `rmw_cyclonedds_cpp`'s (de)serialization, and the liberal use of `std::string` objects internally most likely doesn't help.
It would definitely be interesting to investigate this.

## Tracing

Just in case low-overhead instrumentation is needed to investigate real-time performance issues with rmw_email, I added [LTTng](https://lttng.org/docs) tracepoints.
`rmw_email_cpp` uses the `ros2_tracing` instrumentation & tracepoints for the `rmw` layer.
`email` has its own [LTTng tracepoints](https://github.com/christophebedard/rmw_email/blob/master/email/include/email/lttng.hpp) to collect lower-level information in order to correlate it with the ROS 2 trace data.

## Limitations and future work

Unsurprisingly, there are many limitations, with the main ones being high message latency and low pub/sub rate.
Also, as mentioned previously, messages might be received in the wrong order.
This could be due to Gmail's infrastructure, since having sub-millisecond latencies and guaranteeing that emails are always in the right order are probably not high priorities.
Tackling those limitations might be possible, but it *could* be argued that it's not worth the effort.

Nonetheless, many other paths could be explored.
Type support introspection could be replaced with static type support (i.e., generated code) to try to lower latencies.
Also, although we could compare this to DDS domain IDs, configuration files currently impose a direction on a whole process' communications unless all emails are sent to & from the same address.
Config files could be improved to allow users to specify per-topic or per-namespace email recipients.
Furthermore, the email standards and infrastructure could be leveraged even more to get interesting features.
For example, mailing lists could be used as a form of configurable "multicast."
Finally, message filtering could be achieved by setting up rules in an email client to forward emails based on the messages' content.

## Conclusion

In conclusion, I presented [rmw_email](https://github.com/christophebedard/rmw_email), which contains a standalone middleware as well as a ROS 2 middleware implementation to exchange messages using emails.

ROS 2's abstractions lead to additional complexity and overhead, but they're also quite powerful -- now you can worry about getting ~~SLAM~~ SPAM into your [Nav2](https://navigation.ros.org/) stack!
Ultimately, it's an interesting debate between users who benefit from and need that abstraction, and those who prefer to break it a little bit to have direct access to the underlying middleware.
There might be a better middle ground to be found or even an alternative that allows both to coexist.
Or perhaps the status quo is good for most users, and those who need a more specialized version of ROS 2 can just fork it, as some have done.
Even if rmw_email will never be used in production (or at all), I hope that it can provide some insight and stimulate discussions on this subject.

Aside from that, I think this project had real benefits for the ROS 2 community, both directly and indirectly.
There's of course the separate project to do symmetrical conversions between ROS 2 messages and a YAML representation.
Therefore, email stuff aside, that part is probably a cool contribution to the ROS 2 community!
I also ~~got distracted~~ embraced the open source philosophy along the way.
I started using the ROS 2 tooling working group's GitHub actions, [`setup-ros`](https://github.com/ros-tooling/setup-ros) and [`action-ros-ci`](https://github.com/ros-tooling/action-ros-ci), for rmw_email.
I contributed some improvements and new features that I needed.
Additionally, I made a number of contributions to ROS 2 core packages and ROS 2 dependencies here and there.

Time will tell whether or not this was more useful than my [previous blog post](/ros-tracing-message-flow/).
However, even if I received multiple facepalm emojis 🤦‍♂️ from a friend after sharing my "ROS 2... over email" idea, I would say that, after putting 300+ hours into this project over more than a year, I'm extremely satisfied with the outcome!

{% include figure.html
    url="/assets/img/rmw-email/overall_rmw_email_time_investment.png"
    caption="Time tracking result for rmw_email."
    alt="over 300 hours spent over 14 months on the code itself and around 25 hours spent on this blog post over a few weeks"
%}

## Links

* rmw_email: [github.com/christophebedard/rmw_email](https://github.com/christophebedard/rmw_email)
  * `email` design document: [christophebedard.com/rmw_email/design/email/](https://christophebedard.com/rmw_email/design/email/)
  * `email` API documentation: [christophebedard.com/rmw_email/api/email/](https://christophebedard.com/rmw_email/api/email/)
* dynamic_message_introspection: [github.com/osrf/dynamic_message_introspection](https://github.com/osrf/dynamic_message_introspection)
  * the PR with changes mentioned in this post has now been merged: [github.com/osrf/dynamic_message_introspection/pull/15](https://github.com/osrf/dynamic_message_introspection/pull/15)

## References

{% include ref_dest.html n="1" %}
Z. Jiang, Y. Gong, J. Zhai, Y.-P. Wang, W. Liu, H. Wu, and J. Jin, "Message passing optimization in robot operating system," *International Journal of Parallel Programming*, vol. 48, no. 1, pp. 119--136, 2020.  
{% include ref_dest.html n="2" %}
T. Kronauer, J. Pohlmann, M. Matthe, T. Smejkal, and G. Fettweis, "Latency overhead of ros2 for modular time-critical systems," *arXiv preprint arXiv:2101.02074*, 2021.  
{% include ref_dest.html n="3" %}
[RFC 3501, section 2.3.1.1](https://datatracker.ietf.org/doc/html/rfc3501#section-2.3.1.1)  
{% include ref_dest.html n="4" %}
[RFC 3501, section 6.3.2](https://datatracker.ietf.org/doc/html/rfc3501#section-6.3.2)  
{% include ref_dest.html n="5" %}
[RFC 5322, page 26](https://datatracker.ietf.org/doc/html/rfc5322#page-26)  
